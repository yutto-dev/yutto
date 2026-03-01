from __future__ import annotations

import asyncio
import sys
from asyncio import Queue
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from biliass import BlockOptions
from returns.maybe import Nothing, Some

from yutto.downloader.downloader import DownloadState, process_download
from yutto.exceptions import ErrorCode
from yutto.extractor import (
    BangumiBatchExtractor,
    BangumiExtractor,
    CheeseBatchExtractor,
    CheeseExtractor,
    CollectionExtractor,
    FavouritesExtractor,
    SeriesExtractor,
    UgcVideoBatchExtractor,
    UgcVideoExtractor,
    UserAllFavouritesExtractor,
    UserAllUgcVideosExtractor,
    UserWatchLaterExtractor,
)
from yutto.path_templates import create_unique_path_resolver
from yutto.types import EpisodeData, ExtractorOptions
from yutto.utils.asynclib import sleep_with_status_bar_refresh
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import DanmakuOptions
from yutto.utils.fetcher import Fetcher, create_client
from yutto.utils.time import TIME_FULL_FMT
from yutto.validator import (
    validate_batch_arguments,
    validate_user_info,
)

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from httpx import AsyncClient
    from returns.maybe import Maybe

    from yutto.types import EpisodeData
    from yutto.utils.fetcher import FetcherContext


@dataclass
class DownloadTask:
    args: argparse.Namespace


class DownloadManager:
    queue: Queue[Maybe[DownloadTask]]

    def __init__(self):
        self.queue = Queue()
        self.unique_path = create_unique_path_resolver()
        self.loop_task: Maybe[asyncio.Task[None]] = Nothing

    def start(self, ctx: FetcherContext):
        self.loop_task = Some(asyncio.create_task(self.loop(ctx)))

    async def wait_for_completion(self):
        if self.loop_task == Nothing:
            raise RuntimeError("Task manager is not started.")
        loop_task = self.loop_task.unwrap()
        if loop_task.done():
            return
        await loop_task
        await self.queue.join()

    async def stop(self):
        if self.loop_task == Nothing:
            raise RuntimeError("Task manager is not started.")
        loop_task = self.loop_task.unwrap()
        if loop_task.done():
            return
        while not self.queue.empty():
            await self.queue.get()
            self.queue.task_done()
        await self.queue.join()
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

    async def add_task(self, task: DownloadTask):
        await self.queue.put(Some(task))

    async def add_stop_task(self):
        await self.queue.put(Nothing)

    async def loop(self, ctx: FetcherContext):
        ctx.set_fetch_semaphore(fetch_workers=8)
        async with create_client(
            cookies=ctx.cookies,
            trust_env=ctx.trust_env,
            proxy=ctx.proxy,
        ) as client:
            while True:
                maybe_task = await self.queue.get()
                try:
                    if maybe_task == Nothing:
                        break
                    task = maybe_task.unwrap()
                    await self.process_task(
                        client,
                        ctx,
                        task,
                    )
                finally:
                    self.queue.task_done()

    async def process_task(self, client: AsyncClient, ctx: FetcherContext, task: DownloadTask):
        args = task.args
        # 验证批量参数
        if args.batch:
            validate_batch_arguments(args)

        # 初始化各种提取器
        extractors = (
            [
                UgcVideoBatchExtractor(),  # 投稿全集
                BangumiBatchExtractor(),  # 番剧全集
                CheeseBatchExtractor(),  # 课程全集
                FavouritesExtractor(),  # 用户单一收藏
                UserAllFavouritesExtractor(),  # 用户全部收藏
                SeriesExtractor(),  # 视频列表
                CollectionExtractor(),  # 视频合集
                UserAllUgcVideosExtractor(),  # 个人空间，由于个人空间的正则包含了收藏夹，所以需要放在收藏夹之后
                UserWatchLaterExtractor(),  # 用户稍后再看
            ]
            if args.batch
            else [
                UgcVideoExtractor(),  # 投稿单集
                BangumiExtractor(),  # 番剧单话
                CheeseExtractor(),  # 课程单集
            ]
        )
        url: str = args.url
        # 将 shortcut 转为完整 url
        for extractor in extractors:
            matched, url = extractor.resolve_shortcut(url)
            if matched:
                break

        # 在开始前校验，减少对第一个视频的请求
        if not await validate_user_info(ctx, {"is_login": args.login_strict, "vip_status": args.vip_strict}):
            Logger.error("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")
            sys.exit(ErrorCode.NOT_LOGIN_ERROR.value)
        # 重定向到可识别的 url
        try:
            url = await Fetcher.get_redirected_url(ctx, client, url)
        except httpx.InvalidURL:
            Logger.error(f"无效的 url({url})～请检查一下链接是否正确～")
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)
        except httpx.UnsupportedProtocol:
            error_text = f"无效的 url 协议（{url}）～请检查一下链接协议是否正确"
            if not args.batch:
                error_text += (
                    "，如使用裸 id 功能，请确认该类型 id 是否支持当前单话模式，如不支持需要添加 `-b` 以使用批量模式"
                )
            Logger.error(error_text)
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)

        # 提取信息，构造解析任务～
        for extractor in extractors:
            if extractor.match(url):
                download_list = await extractor(
                    ctx,
                    client,
                    ExtractorOptions(
                        episodes=args.episodes,
                        with_section=args.with_section,
                        require_video=args.require_video,
                        require_audio=args.require_audio,
                        require_danmaku=args.require_danmaku,
                        require_subtitle=args.require_subtitle,
                        require_metadata=args.require_metadata,
                        require_cover=args.require_cover,
                        require_chapter_info=args.require_chapter_info,
                        danmaku_format=args.danmaku_format,
                        subpath_template=args.subpath_template,
                        ai_translation_language=args.ai_translation_language,
                    ),
                )
                break
        else:
            if args.batch:
                # TODO: 指向文档中受支持的列表部分
                Logger.error("url 不正确呦～")
            else:
                Logger.error("url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～")
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)

        current_download_state = DownloadState.SKIP

        # 下载～
        for i, episode_data_coro in enumerate(download_list):
            if episode_data_coro is None:
                continue

            # 中途校验，因为批量下载时可能会失效
            if not await validate_user_info(ctx, {"is_login": args.login_strict, "vip_status": args.vip_strict}):
                Logger.error("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")
                sys.exit(ErrorCode.NOT_LOGIN_ERROR.value)

            if current_download_state != DownloadState.SKIP and args.download_interval > 0:
                Logger.info(f"下载间隔 {args.download_interval} 秒")
                await sleep_with_status_bar_refresh(args.download_interval)

            # 这时候才真正开始解析链接
            episode_data = await episode_data_coro
            if episode_data is None:
                continue
            # 保证路径唯一
            episode_data = ensure_unique_path(episode_data, self.unique_path)
            if args.batch:
                Logger.custom(
                    f"{episode_data['path'].name}",
                    Badge(f"[{i + 1}/{len(download_list)}]", fore="black", back="cyan"),
                )

            current_download_state = await process_download(
                ctx,
                client,
                episode_data,
                {
                    "output_dir": args.dir,
                    "tmp_dir": args.tmp_dir or args.dir,
                    "require_video": args.require_video,
                    "require_chapter_info": args.require_chapter_info,
                    "video_quality": args.video_quality,
                    "video_download_codec": args.vcodec.split(":")[0],
                    "video_save_codec": args.vcodec.split(":")[1],
                    "video_download_codec_priority": args.download_vcodec_priority,
                    "require_audio": args.require_audio,
                    "audio_quality": args.audio_quality,
                    "audio_download_codec": args.acodec.split(":")[0],
                    "audio_save_codec": args.acodec.split(":")[1],
                    "output_format": args.output_format,
                    "output_format_audio_only": args.output_format_audio_only,
                    "overwrite": args.overwrite,
                    "block_size": int(args.block_size * 1024 * 1024),
                    "num_workers": args.num_workers,
                    "save_cover": args.save_cover,
                    "metadata_format": {
                        "premiered": args.metadata_format_premiered,
                        "dateadded": TIME_FULL_FMT,
                    },
                    "banned_mirrors_pattern": args.banned_mirrors_pattern,
                    "danmaku_options": parse_danmaku_options(args),
                },
            )
            Logger.new_line()
        Logger.new_line()


def ensure_unique_path(episode_data: EpisodeData, unique_name_resolver: Callable[[str], str]) -> EpisodeData:
    original_path = episode_data["path"]
    new_path = Path(unique_name_resolver(str(original_path)))
    episode_data["path"] = new_path
    if original_path != new_path:
        Logger.warning(f"文件名重复，已重命名为 {new_path.name}")
    return episode_data


def parse_danmaku_options(args: argparse.Namespace) -> DanmakuOptions:
    block_options = BlockOptions(
        block_top=args.danmaku_block_top or args.danmaku_block_fixed,
        block_bottom=args.danmaku_block_bottom or args.danmaku_block_fixed,
        block_scroll=args.danmaku_block_scroll,
        block_reverse=args.danmaku_block_reverse,
        block_special=args.danmaku_block_special,
        block_colorful=args.danmaku_block_colorful,
        block_keyword_patterns=(args.danmaku_block_keyword_patterns or []),
    )
    return DanmakuOptions(
        font_size=args.danmaku_font_size,
        font=args.danmaku_font,
        opacity=args.danmaku_opacity,
        display_region_ratio=args.danmaku_display_region_ratio,
        speed=args.danmaku_speed,
        block_options=block_options,
    )
