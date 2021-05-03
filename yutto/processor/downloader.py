import asyncio
import os
import time
from typing import Any, Optional

import aiohttp
from aiofiles import os as aioos

from yutto.api.types import AudioUrlMeta, VideoUrlMeta
from yutto.processor.filter import filter_none_value, select_audio, select_video
from yutto.utils.asynclib import CoroutineTask, parallel_with_limit
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.processor.progressor import show_progress


def slice(start: int, total_size: Optional[int], block_size: Optional[int] = None) -> list[tuple[int, Optional[int]]]:
    """生成分块后的 (start, size) 序列

    Args:
        start (int): 总起始位置
        total_size (Optional[int]): 需要分块的总大小
        block_size (Optional[int], optional): 每块的大小. Defaults to None.

    Returns:
        list[tuple[int, Optional[int]]]: 分块大小序列，使用元组组织，格式为 (start, size)
    """
    if total_size is None:
        return [(0, None)]
    if block_size is None:
        return [(0, total_size - 1)]
    assert start <= total_size, "起始地址（{}）大于总地址（{}）".format(start, total_size)
    offset_list: list[tuple[int, Optional[int]]] = [(i, block_size) for i in range(start, total_size, block_size)]
    if (total_size - start) % block_size != 0:
        offset_list[-1] = (
            start + (total_size - start) // block_size * block_size,
            total_size - start - (total_size - start) // block_size * block_size,
        )
    return offset_list


def combine(*l_list: list[Any]) -> list[Any]:
    """将多个 list 「均匀」地合并到一个 list

    # example

    ```
    l_list = [
        [1, 2, 3, 4, 5],
        [6, 7, 8],
        [9, 10, 11, 12]
    ]
    combine(l_list)
    # [1, 6, 9, 2, 7, 10, 3, 8, 11, 4, 12, 5]
    ```
    """
    results: list[Any] = []
    for i in range(max([len(l) for l in l_list])):
        for l in l_list:
            if i < len(l):
                results.append(l[i])
    return results


async def download_video(
    session: aiohttp.ClientSession,
    videos: list[VideoUrlMeta],
    audios: list[AudioUrlMeta],
    output_dir: str,
    file_name: str,
    # TODO: options 使用 TypedDict
    options: Any,
):
    video_path = os.path.join(output_dir, file_name + "_video.m4s")
    audio_path = os.path.join(output_dir, file_name + "_audio.m4s")
    output_path_template = os.path.join(output_dir, file_name + "{output_format}")
    ffmpeg = FFmpeg()

    # TODO: 显示全部 Videos、Audios 信息
    video = select_video(videos, options["require_video"], options["video_quality"], options["video_download_codec"])
    audio = select_audio(audios, options["require_audio"], options["audio_quality"], options["audio_download_codec"])
    # TODO: 显示被选中的 Video、Audio 信息

    output_format = ".mp4" if video is not None else ".aac"
    output_path = output_path_template.format(output_format=output_format)
    if not options["overwrite"] and os.path.exists(output_path):
        Logger.info("文件 {} 已存在".format(file_name))
        return

    # idx_video = -1
    # if video is not None:
    #     idx_video = videos.index(video)
    # Logger.info(f"视频 {file_name} 共包含以下 {len(videos)} 个视频流：")
    # videos_log = [
    #     "{:02} [{:>4}] [{:>4}x{:>4}] <{:>10}>".format(
    #         i,
    #         video["codec"].upper(),
    #         video["width"],
    #         video["height"],
    #         video_quality_map[video["quality"]]["description"],
    #     )
    #     for i, video in enumerate(videos)
    # ]

    # for video_log in videos_log:
    #     Logger.info(video_log)

    if video is None and audio is None:
        return
    buffers: list[Optional[AsyncFileBuffer]] = [None, None]
    sizes: list[Optional[int]] = [None, None]
    task_funcs: list[list[CoroutineTask]] = []
    if video is not None:
        vbuf = await AsyncFileBuffer.create(video_path, overwrite=options["overwrite"])
        vsize = await Fetcher.get_size(session, video["url"])
        vtask_funcs = [
            Fetcher.download_file_with_offset(session, video["url"], video["mirrors"], vbuf, offset, block_size)
            for offset, block_size in slice(vbuf.written_size, vsize, options["block_size"])
        ]
        task_funcs.append(vtask_funcs)
        buffers[0], sizes[0] = vbuf, vsize

    if audio is not None:
        abuf = await AsyncFileBuffer.create(audio_path, overwrite=options["overwrite"])
        asize = await Fetcher.get_size(session, audio["url"])
        atask_funcs = [
            Fetcher.download_file_with_offset(session, audio["url"], audio["mirrors"], abuf, offset, block_size)
            for offset, block_size in slice(abuf.written_size, asize, options["block_size"])
        ]
        task_funcs.append(atask_funcs)
        buffers[1], sizes[1] = abuf, asize

    tasks = parallel_with_limit(combine(*task_funcs), num_workers=options["num_workers"])
    tasks.append(asyncio.create_task(show_progress(filter_none_value(buffers), sum(filter_none_value(sizes)))))

    Logger.info(f"开始下载 {file_name}……")
    for task in tasks:
        await task
    Logger.info("下载完成！")

    if video is not None:
        await vbuf.close()
    if audio is not None:
        await abuf.close()

    # TODO: 将 merge 分离出去？
    Logger.info(f"开始合并 {file_name}……")
    # fmt: off
    args: list[str] = []
    if video is not None:
        args.extend([
            "-i", video_path,
        ])
    if audio is not None:
        args.extend([
            "-i", audio_path,
        ])
    if video is not None:
        args.extend([
            "-vcodec", options["video_save_codec"],
        ])
    if audio is not None:
        args.extend([
            "-acodec", options["audio_save_codec"],
        ])
    args.extend(["-y"])

    args.append(output_path)
    ffmpeg.exec(args)
    # fmt: on
    Logger.info("合并完成！")

    if video is not None:
        await aioos.remove(video_path)
    if audio is not None:
        await aioos.remove(audio_path)
