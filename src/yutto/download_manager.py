from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from biliass import BlockOptions

from yutto.api.user_info import validate_user_info
from yutto.core.events import DownloadItemListed, DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event
from yutto.core.result import DownloadResult, ItemResult, ResolvedItem, ResolveFailure, ResolveResult
from yutto.downloader.downloader import process_download
from yutto.exceptions import NotLoginError, ResolveFailedError, WrongArgumentError, WrongUrlError
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
from yutto.extractor._abc import StreamingBatchExtractor
from yutto.path_templates import create_unique_path_resolver
from yutto.types import EpisodeData, ExtractorOptions
from yutto.utils.asynclib import sleep_with_status_bar_refresh
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import DanmakuOptions
from yutto.utils.fetcher import Fetcher, create_client, unwrap_fetch_result
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.time import TIME_FULL_FMT
from yutto.validator import validate_batch_selection

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from httpx import AsyncClient

    from yutto.core.request import DanmakuRequestOptions, DownloadRequest
    from yutto.exceptions import YuttoBaseException
    from yutto.extractor._abc import EpisodeListedCallback
    from yutto.extractor.outcome import ResolveOutcome
    from yutto.types import EpisodeData, EpisodeInfo, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


def show_batch_episode_title(
    episode_info: EpisodeInfo, index: int, total: int, current_display_group: str | None
) -> str | None:
    """打印批量下载中的单集标题，多分 p 视频额外输出分组标题行。

    当 display_group 发生变化时（多分 p 视频切换到新标题），先用「列表」徽章
    打印分组名，然后以缩进格式打印分 p 名；单集视频直接打印文件名。

    Args:
        episode_info: 当前条目的稳定信息，包含 path 和 display_group。
        index: 当前条目在下载列表中的序号（从 1 开始）。
        total: 下载列表总条目数。
        current_display_group: 上一条目的 display_group，用于检测分组切换。

    Returns:
        更新后的 current_display_group，供下一次调用使用。
    """
    display_group = episode_info["display_group"]
    # 分组变化时打印分组标题（多分 p 视频新出现或切换到另一个多分 p 视频）
    if display_group is not None and display_group != current_display_group:
        Logger.custom(display_group, Badge("列表", fore="black", back="cyan"))
        current_display_group = display_group
    elif display_group is None:
        current_display_group = None

    display_name = episode_info["path"].name
    if display_group is not None:
        # 多分 p 条目缩进显示，以区分分组标题行
        display_name = f"  {display_name}"
    Logger.custom(
        display_name,
        Badge(f"[{index}/{total}]", fore="black", back="cyan"),
    )
    return current_display_group


def _resolved_item_from(episode: ResolvableEpisode) -> ResolvedItem:
    info = episode.info
    return ResolvedItem(
        avid=str(info["avid"]),
        cid=str(info["cid"]),
        url=info["url"],
        name=info["name"],
        title=info["title"],
        cover_url=info["cover_url"],
        planned_path=info["path"],
        display_group=info["display_group"],
        uploader=info["uploader"],
        description=info["description"],
        tags=tuple(info["tags"]),
    )


def _emit_item_listed(episode: ResolvableEpisode) -> None:
    item = _resolved_item_from(episode)
    emit_download_event(
        DownloadItemListed(
            avid=item.avid,
            cid=item.cid,
            url=item.url,
            name=item.name,
            title=item.title,
            cover_url=item.cover_url,
            planned_path=item.planned_path,
            display_group=item.display_group,
            uploader=item.uploader,
            description=item.description,
            tags=item.tags,
        )
    )


def _resolved_item_key(episode: ResolvableEpisode) -> tuple[str, str, str, Path, str | None]:
    """Return a stable occurrence key for matching streamed and final items."""
    info = episode.info
    return (
        str(info["avid"]),
        str(info["cid"]),
        info["url"],
        info["path"],
        info["display_group"],
    )


@dataclass(frozen=True, slots=True)
class _ResolvedItemsOutcome:
    items: tuple[ResolvedItem, ...]
    failures: tuple[YuttoBaseException, ...]


class DownloadManager:
    """Execute download requests sequentially in one shared network session."""

    def __init__(self):
        self.unique_path = create_unique_path_resolver()

    async def execute(self, ctx: FetcherContext, requests: Sequence[DownloadRequest]) -> DownloadResult:
        """Run requests in order while sharing the client and path allocator."""
        items: list[ItemResult] = []
        ctx.set_fetch_semaphore(fetch_workers=ctx.fetch_workers)
        async with create_client(
            cookies=ctx.cookies,
            trust_env=ctx.trust_env,
            proxy=ctx.proxy,
        ) as client:
            for request in requests:
                items.extend(await self.process_request(client, ctx, request))
        return DownloadResult(items=tuple(items))

    async def execute_resolve(self, ctx: FetcherContext, requests: Sequence[DownloadRequest]) -> ResolveResult:
        """Enumerate episodes for requests in order without downloading anything."""
        items: list[ResolvedItem] = []
        failures: list[YuttoBaseException] = []
        ctx.set_fetch_semaphore(fetch_workers=ctx.fetch_workers)
        async with create_client(
            cookies=ctx.cookies,
            trust_env=ctx.trust_env,
            proxy=ctx.proxy,
        ) as client:
            for request in requests:
                outcome = await self.resolve_items(client, ctx, request)
                items.extend(outcome.items)
                failures.extend(outcome.failures)
        if failures and not items:
            # 存在预期内失败且没有任何条目解析成功：任务失败而非空成功。
            # 单一失败直接抛原始异常，wire 上保留其稳定错误码（如 not found）；
            # 纯过滤导致的空结果（无失败上报，如时间过滤/空收藏夹）仍是 completed 空结果
            if len(failures) == 1:
                raise failures[0]
            raise ResolveFailedError(f"解析未得到任何条目：{len(failures)} 个来源/条目解析失败（详见 server 日志）")
        resolved_failures = tuple(
            ResolveFailure(type=type(error).__name__, message=error.message, code=error.code.value)
            for error in failures
        )
        return ResolveResult(items=tuple(items), failures=resolved_failures)

    async def resolve_items(
        self,
        client: AsyncClient,
        ctx: FetcherContext,
        request: DownloadRequest,
    ) -> _ResolvedItemsOutcome:
        """List the stable episode snapshots of one request; the volatile data is never fetched.

        返回的 planned_path 是模板解析出的计划路径；实际下载时可能因去重而调整。
        item_listed 逐条推送：支持流式的 batch 提取器通过显式 on_item 回调在
        每个视频解析完成时交出分集，提取结束后这里只补发未流式推送过的条目；
        返回列表始终保持提取器的原始顺序。
        """
        emitted: set[tuple[str, str, str, Path, str | None]] = set()

        async def stream_episode(episode: ResolvableEpisode) -> None:
            key = _resolved_item_key(episode)
            if key in emitted:
                await asyncio.sleep(0)
                return
            emitted.add(key)
            _emit_item_listed(episode)
            await asyncio.sleep(0)

        outcome = await self.resolve_request(client, ctx, request, on_item=stream_episode)
        items: list[ResolvedItem] = []
        for episode in outcome.items:
            key = _resolved_item_key(episode)
            if key not in emitted:
                emitted.add(key)
                _emit_item_listed(episode)
                # 未流式化的提取器仍会在这个无 await 的循环里整批产出 item_listed；
                # 逐条让出控制权给事件消费者（如 server 每连接的 sender），
                # 避免超出其发送队列容量触发 slow-consumer 断连
                await asyncio.sleep(0)
            items.append(_resolved_item_from(episode))
        return _ResolvedItemsOutcome(items=tuple(items), failures=outcome.failures)

    async def process_request(
        self,
        client: AsyncClient,
        ctx: FetcherContext,
        request: DownloadRequest,
    ) -> tuple[ItemResult, ...]:
        outcome = await self.resolve_request(client, ctx, request)
        download_list = outcome.items

        item_results: list[ItemResult] = []
        previous_result: ItemResult | None = None
        current_display_group: str | None = None

        # 下载～
        for i, episode in enumerate(download_list):
            # 中途校验基于请求级缓存的用户信息（见 get_user_info），不会重复请求；
            # 凭据若在过程中失效，需等缓存所在的 FetcherContext 重建后才能被发现
            if not await validate_user_info(
                ctx,
                {"is_login": request.access.login_strict, "vip_status": request.access.vip_strict},
            ):
                raise NotLoginError("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")

            if (
                previous_result is not None
                and previous_result.has_downloaded_media
                and request.network.download_interval > 0
            ):
                Logger.info(f"下载间隔 {request.network.download_interval} 秒")
                await sleep_with_status_bar_refresh(request.network.download_interval)

            # 这时候才真正开始解析链接
            episode_data = await episode.resolve_data()
            if episode_data is None:
                continue
            # 保证路径唯一
            episode_data = ensure_unique_path(episode_data, self.unique_path)
            if request.output.enforce_directory_boundary:
                ensure_output_path_is_scoped(
                    episode_data["info"]["path"],
                    request.output.directory,
                    request.output.temporary_directory or request.output.directory,
                )
            if request.scope.batch:
                current_display_group = show_batch_episode_title(
                    episode_data["info"],
                    i + 1,
                    len(download_list),
                    current_display_group,
                )

            previous_result = await process_download(
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
            item_results.append(previous_result)
            Logger.new_line()
        Logger.new_line()
        return tuple(item_results)

    async def resolve_request(
        self,
        client: AsyncClient,
        ctx: FetcherContext,
        request: DownloadRequest,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        """Match the request to an extractor and run its listing phase."""
        publication_time_filter = PublicationTimeFilter.from_strings(
            request.selection.start_time,
            request.selection.end_time,
        )
        # 验证批量参数
        if request.scope.batch:
            validate_batch_selection(request.selection.episodes)
        emit_download_event(DownloadStageChanged(name=DownloadStage.RESOLVING))

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
                extractor_options = ExtractorOptions(
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
                    publication_time_filter=publication_time_filter,
                )
                if on_item is not None and isinstance(extractor, StreamingBatchExtractor):
                    download_list = await extractor(ctx, client, extractor_options, on_item=on_item)
                else:
                    download_list = await extractor(ctx, client, extractor_options)
                break
        else:
            if request.scope.batch:
                # TODO: 指向文档中受支持的列表部分
                error_text = "url 不正确呦～"
            else:
                error_text = "url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～"
            raise WrongUrlError(error_text)

        return download_list


def ensure_unique_path(episode_data: EpisodeData, unique_name_resolver: Callable[[str], str]) -> EpisodeData:
    original_path = episode_data["info"]["path"]
    new_path = Path(unique_name_resolver(str(original_path)))
    episode_data["info"]["path"] = new_path
    if original_path != new_path:
        Logger.warning(f"文件名重复，已重命名为 {new_path.name}")
    return episode_data


def ensure_output_path_is_scoped(path: Path, output_root: Path, temporary_root: Path) -> None:
    # anchor 检查覆盖 Windows 上 is_absolute() 为 False 的盘符相对/根路径（如 "/x"、"C:x"）
    if path.is_absolute() or path.anchor or ".." in path.parts:
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
