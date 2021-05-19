import asyncio
import functools
import os
from typing import Any, Optional

import aiohttp

from yutto.api.types import AudioUrlMeta, MultiLangSubtitle, VideoUrlMeta
from yutto.media.quality import audio_quality_map, video_quality_map
from yutto.processor.filter import filter_none_value, select_audio, select_video
from yutto.processor.progressbar import show_progress
from yutto.utils.asynclib import CoroutineTask, parallel_with_limit
from yutto.utils.console.colorful import colored_string
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import DanmakuData, write_danmaku
from yutto.utils.fetcher import Fetcher
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.subtitle import write_subtitle


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


def show_videos_info(videos: list[VideoUrlMeta], selected: int):
    if not videos:
        Logger.info("不包含任何视频流")
        return
    Logger.info(f"共包含以下 {len(videos)} 个视频流：")
    for i, video in enumerate(videos):
        log = "{}{:2} [{:^4}] [{:>4}x{:<4}] <{:^8}> #{}".format(
            "*" if i == selected else " ",
            i,
            video["codec"].upper(),
            video["width"],
            video["height"],
            video_quality_map[video["quality"]]["description"],
            len(video["mirrors"]) + 1,
        )
        if i == selected:
            log = colored_string(log, fore="blue")
        Logger.info(log)


def show_audios_info(audios: list[AudioUrlMeta], selected: int):
    if not audios:
        Logger.info("不包含任何音频流")
        return
    Logger.info(f"共包含以下 {len(audios)} 个音频流：")
    for i, audio in enumerate(audios):
        log = "{}{:2} [{:^4}] <{:^8}>".format(
            "*" if i == selected else " ", i, audio["codec"].upper(), audio_quality_map[audio["quality"]]["description"]
        )
        if i == selected:
            log = colored_string(log, fore="magenta")
        Logger.info(log)


# TODO: 逻辑拆分
async def download_video(
    session: aiohttp.ClientSession,
    videos: list[VideoUrlMeta],
    audios: list[AudioUrlMeta],
    output_dir: str,
    file_name: str,
    subtitles: list[MultiLangSubtitle],
    danmaku: DanmakuData,
    # TODO: options 使用 TypedDict
    options: Any,
):
    Logger.info("开始处理视频 {}".format(file_name))
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    output_path_no_ext = os.path.join(output_dir, file_name)
    video_path = output_path_no_ext + "_video.m4s"
    audio_path = output_path_no_ext + "_audio.m4s"
    ffmpeg = FFmpeg()

    video = select_video(videos, options["require_video"], options["video_quality"], options["video_download_codec"])
    audio = select_audio(audios, options["require_audio"], options["audio_quality"], options["audio_download_codec"])

    # 显示音视频详细信息
    show_videos_info(videos, videos.index(video) if video is not None else -1)
    show_audios_info(audios, audios.index(audio) if audio is not None else -1)

    output_format = ".mp4" if video is not None else ".aac"
    output_path = output_path_no_ext + output_format
    if os.path.exists(output_path):
        if not options["overwrite"]:
            Logger.info("文件 {} 已存在".format(file_name))
            return
        else:
            Logger.info("文件已存在，因启用 overwrite 选项强制删除……")
            os.remove(output_path)

    if video is None and audio is None:
        Logger.warning("没有音视频需要下载")
        return

    # 保存字幕
    if subtitles:
        for subtitle in subtitles:
            write_subtitle(subtitle["lines"], output_path, subtitle["lang"])
        Logger.custom(
            "{} 字幕已全部生成".format(", ".join([subtitle["lang"] for subtitle in subtitles])),
            badge=Badge("字幕", fore="black", back="cyan"),
        )

    # 保存弹幕
    if danmaku["data"]:
        write_danmaku(
            danmaku,
            output_path,
            video["height"] if video is not None else 0,
            video["width"] if video is not None else 0,
        )
        Logger.custom("{} 弹幕已生成".format(danmaku["save_type"]).upper(), badge=Badge("弹幕", fore="black", back="cyan"))

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

    Logger.info(f"开始下载……")
    for task in tasks:
        await task
    Logger.info("下载完成！")

    if video is not None:
        await vbuf.close()
    if audio is not None:
        await abuf.close()

    # TODO: 将 merge 分离出去？
    Logger.info(f"开始合并……")
    # fmt: off
    args_list: list[list[str]] = [
        ["-i", video_path] if video is not None else [],
        ["-i", audio_path] if audio is not None else [],
        ["-vcodec", options["video_save_codec"]] if video is not None else [],
        ["-acodec", options["audio_save_codec"]] if video is not None else [],
        ["-y", output_path]
    ]

    ffmpeg.exec(functools.reduce(lambda prev, cur: prev+cur, args_list))
    # fmt: on
    Logger.info("合并完成！")

    if video is not None:
        os.remove(video_path)
    if audio is not None:
        os.remove(audio_path)
