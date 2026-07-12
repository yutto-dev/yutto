from __future__ import annotations

import asyncio
from asyncio import Queue
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from biliass import BlockOptions
from returns.maybe import Nothing, Some

from yutto.api.user_info import validate_user_info
from yutto.downloader.downloader import DownloadState, process_download
from yutto.exceptions import NotLoginError, WrongArgumentError, WrongUrlError
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
from yutto.utils.fetcher import Fetcher, create_client, unwrap_fetch_result
from yutto.utils.filter import Filter
from yutto.utils.time import TIME_FULL_FMT
from yutto.validator import validate_batch_selection

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from returns.maybe import Maybe

    from yutto.core.request import DanmakuRequestOptions, DownloadRequest
    from yutto.types import EpisodeData
    from yutto.utils.fetcher import FetcherContext


@dataclass
class DownloadTask:
    request: DownloadRequest


def show_batch_episode_title(
    episode_data: EpisodeData, index: int, total: int, current_display_group: str | None
) -> str | None:
    """打印批量下载中的单集标题，多分 p 视频额外输出分组标题行。

    当 display_group 发生变化时（多分 p 视频切换到新标题），先用「列表」徽章
    打印分组名，然后以缩进格式打印分 p 名；单集视频直接打印文件名。

    Args:
        episode_data: 当前剧集数据，包含 path 和 display_group。
        index: 当前条目在下载列表中的序号（从 1 开始）。
        total: 下载列表总条目数。
        current_display_group: 上一条目的 display_group，用于检测分组切换。

    Returns:
        更新后的 current_display_group，供下一次调用使用。
    """
    display_group = episode_data["display_group"]
    # 分组变化时打印分组标题（多分 p 视频新出现或切换到另一个多分 p 视频）
    if display_group is not None and display_group != current_display_group:
        Logger.custom(display_group, Badge("列表", fore="black", back="cyan"))
        current_display_group = display_group
    elif display_group is None:
        current_display_group = None

    display_name = episode_data["path"].name
    if display_group is not None:
        # 多分 p 条目缩进显示，以区分分组标题行
        display_name = f"  {display_name}"
    Logger.custom(
        display_name,
        Badge(f"[{index}/{total}]", fore="black", back="cyan"),
    )
    return current_display_group


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
        ctx.set_fetch_semaphore(fetch_workers=ctx.fetch_workers)
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
        request = task.request
        Filter.configure(request.selection.start_time, request.selection.end_time)
        # 验证批量参数
        if request.scope.batch:
            validate_batch_selection(request.selection.episodes)

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
            if request.scope.batch
            else [
                UgcVideoExtractor(),  # 投稿单集
                BangumiExtractor(),  # 番剧单话
                CheeseExtractor(),  # 课程单集
            ]
        )
        url = request.source.url
        # 将 shortcut 转为完整 url
        for extractor in extractors:
            matched, url = extractor.resolve_shortcut(url)
            if matched:
                break

        # 在开始前校验，减少对第一个视频的请求
        if not await validate_user_info(
            ctx,
            {"is_login": request.access.login_strict, "vip_status": request.access.vip_strict},
        ):
            raise NotLoginError("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")
        # 重定向到可识别的 url
        try:
            url = unwrap_fetch_result(await Fetcher.get_redirected_url(ctx, client, url))
        except httpx.InvalidURL:
            raise WrongUrlError(f"无效的 url({url})～请检查一下链接是否正确～") from None
        except httpx.UnsupportedProtocol:
            error_text = f"无效的 url 协议（{url}）～请检查一下链接协议是否正确"
            if not request.scope.batch:
                error_text += (
                    "，如使用裸 id 功能，请确认该类型 id 是否支持当前单话模式，如不支持需要添加 `-b` 以使用批量模式"
                )
            raise WrongUrlError(error_text) from None

        # 提取信息，构造解析任务～
        for extractor in extractors:
            if extractor.match(url):
                download_list = await extractor(
                    ctx,
                    client,
                    ExtractorOptions(
                        episodes=request.selection.episodes,
                        with_section=request.scope.with_section,
                        require_video=request.resources.video,
                        require_audio=request.resources.audio,
                        require_danmaku=request.resources.danmaku,
                        require_subtitle=request.resources.subtitle,
                        require_metadata=request.resources.metadata,
                        require_cover=request.resources.cover,
                        require_chapter_info=request.resources.chapter_info,
                        danmaku_format=request.danmaku.format,
                        subpath_template=request.output.subpath_template,
                        ai_translation_language=request.resources.ai_translation_language,
                    ),
                )
                break
        else:
            if request.scope.batch:
                # TODO: 指向文档中受支持的列表部分
                error_text = "url 不正确呦～"
            else:
                error_text = "url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～"
            raise WrongUrlError(error_text)

        current_download_state = DownloadState.SKIP
        current_display_group: str | None = None

        # 下载～
        for i, episode_data_coro in enumerate(download_list):
            if episode_data_coro is None:
                continue

            # 中途校验，因为批量下载时可能会失效
            if not await validate_user_info(
                ctx,
                {"is_login": request.access.login_strict, "vip_status": request.access.vip_strict},
            ):
                raise NotLoginError("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")

            if current_download_state != DownloadState.SKIP and request.network.download_interval > 0:
                Logger.info(f"下载间隔 {request.network.download_interval} 秒")
                await sleep_with_status_bar_refresh(request.network.download_interval)

            # 这时候才真正开始解析链接
            episode_data = await episode_data_coro
            if episode_data is None:
                continue
            # 保证路径唯一
            episode_data = ensure_unique_path(episode_data, self.unique_path)
            if request.output.enforce_directory_boundary:
                ensure_output_path_is_scoped(
                    episode_data["path"],
                    request.output.directory,
                    request.output.temporary_directory or request.output.directory,
                )
            if request.scope.batch:
                current_display_group = show_batch_episode_title(
                    episode_data,
                    i + 1,
                    len(download_list),
                    current_display_group,
                )

            current_download_state = await process_download(
                ctx,
                client,
                episode_data,
                {
                    "output_dir": request.output.directory,
                    "tmp_dir": request.output.temporary_directory or request.output.directory,
                    "require_video": request.resources.video,
                    "require_chapter_info": request.resources.chapter_info,
                    "video_quality": request.stream.video_quality,
                    "video_download_codec": request.stream.video_download_codec,
                    "video_save_codec": request.stream.video_save_codec,
                    "video_download_codec_priority": request.stream.video_download_codec_priority,
                    "require_audio": request.resources.audio,
                    "audio_quality": request.stream.audio_quality,
                    "audio_download_codec": request.stream.audio_download_codec,
                    "audio_save_codec": request.stream.audio_save_codec,
                    "output_format": request.output.format,
                    "output_format_audio_only": request.output.audio_only_format,
                    "overwrite": request.output.overwrite,
                    "block_size": request.network.block_size_bytes,
                    "num_workers": request.network.download_workers,
                    "save_cover": request.resources.save_cover,
                    "metadata_format": {
                        "premiered": request.output.metadata_format_premiered,
                        "dateadded": TIME_FULL_FMT,
                    },
                    "banned_mirrors_pattern": request.network.banned_mirrors_pattern,
                    "danmaku_options": create_danmaku_options(request.danmaku),
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


def ensure_output_path_is_scoped(path: Path, output_root: Path, temporary_root: Path) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise WrongArgumentError("解析后的输出路径超出了 server 配置的根目录")
    for root in (output_root.resolve(), temporary_root.resolve()):
        if not (root / path).resolve().is_relative_to(root):
            raise WrongArgumentError("解析后的输出路径超出了 server 配置的根目录")


def create_danmaku_options(options: DanmakuRequestOptions) -> DanmakuOptions:
    block_options = BlockOptions(
        block_top=options.block_top,
        block_bottom=options.block_bottom,
        block_scroll=options.block_scroll,
        block_reverse=options.block_reverse,
        block_special=options.block_special,
        block_colorful=options.block_colorful,
        block_keyword_patterns=options.block_keyword_patterns,
    )
    return DanmakuOptions(
        font_size=options.font_size,
        font=options.font,
        opacity=options.opacity,
        display_region_ratio=options.display_region_ratio,
        speed=options.speed,
        block_options=block_options,
    )
