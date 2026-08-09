from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from yutto._native import InvalidUrlError, UnsupportedProtocolError
from yutto.api.user_info import validate_user_info
from yutto.core.events import DownloadItemListed, DownloadStage, DownloadStageChanged
from yutto.core.operation import ReportLevel, emit_download_event, emit_download_report
from yutto.core.result import DownloadResult, ItemResult, ResolvedItem, ResolveFailure, ResolveResult
from yutto.downloader.downloader import process_download
from yutto.downloader.path_leases import DownloadPathLeasePool
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
from yutto.extractor._abc import BatchExtractor
from yutto.input_parser import validate_batch_selection
from yutto.path_templates import create_unique_path_resolver
from yutto.types import EpisodeData, ExtractorOptions
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result
from yutto.utils.filter import PublicationTimeFilter

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from yutto.core.execution import ExecutionScope, ExecutionScopeFactory
    from yutto.core.request import DownloadRequest
    from yutto.exceptions import YuttoBaseException
    from yutto.extractor._abc import EpisodeListedCallback
    from yutto.extractor.outcome import ResolveOutcome
    from yutto.types import EpisodeInfo, ResolvableEpisode


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
    display_group = episode_info["listing"].display_group
    # 分组变化时打印分组标题（多分 p 视频新出现或切换到另一个多分 p 视频）
    if display_group is not None and display_group != current_display_group:
        emit_download_report(display_group, badge="列表")
        current_display_group = display_group
    elif display_group is None:
        current_display_group = None

    display_name = episode_info["path"].name
    if display_group is not None:
        # 多分 p 条目缩进显示，以区分分组标题行
        display_name = f"  {display_name}"
    emit_download_report(display_name, badge=f"[{index}/{total}]")
    return current_display_group


def _emit_item_listed(item: ResolvedItem) -> None:
    emit_download_event(DownloadItemListed(item=item))


@dataclass(eq=False, slots=True)
class _StreamedResolvedItem:
    episode: ResolvableEpisode
    item: ResolvedItem
    consumed: bool = False


@dataclass(frozen=True, slots=True)
class _ResolvedItemsOutcome:
    items: tuple[ResolvedItem, ...]
    failures: tuple[YuttoBaseException, ...]


class DownloadManager:
    """Execute requests with bounded item concurrency and one explicit scope per request."""

    def __init__(self, *, jobs: int = 1, path_leases: DownloadPathLeasePool | None = None):
        if jobs < 1:
            raise ValueError("jobs must be at least 1")
        self.jobs = jobs
        self.unique_path = create_unique_path_resolver()
        self.path_leases = path_leases or DownloadPathLeasePool()
        self._item_limiter = asyncio.Semaphore(jobs)

    async def execute(
        self,
        scope_factory: ExecutionScopeFactory,
        requests: Sequence[DownloadRequest],
    ) -> DownloadResult:
        """Run requests with request-scoped network state and stable result ordering."""
        results: list[tuple[ItemResult, ...] | None] = [None] * len(requests)
        next_index = 0
        failed = False

        async def run_requests() -> None:
            nonlocal failed, next_index
            while not failed and next_index < len(requests):
                index = next_index
                next_index += 1
                request = requests[index]
                try:
                    async with scope_factory.open(request) as scope:
                        results[index] = await self.process_request(scope, request)
                except BaseException:
                    failed = True
                    raise

        tasks = [
            asyncio.create_task(run_requests(), name=f"yutto-request-worker-{index}")
            for index in range(min(self.jobs, len(requests)))
        ]
        await _gather_cancelling(tasks)
        return DownloadResult(items=tuple(item for result in results if result is not None for item in result))

    async def execute_resolve(
        self,
        scope_factory: ExecutionScopeFactory,
        requests: Sequence[DownloadRequest],
    ) -> ResolveResult:
        """Enumerate episodes for requests in order without downloading anything."""
        items: list[ResolvedItem] = []
        failures: list[YuttoBaseException] = []
        for request in requests:
            async with scope_factory.open(request) as scope:
                outcome = await self.resolve_items(scope, request)
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
        scope: ExecutionScope,
        request: DownloadRequest,
    ) -> _ResolvedItemsOutcome:
        """List the stable episode snapshots of one request; the volatile data is never fetched.

        返回的 planned_path 是模板解析出的计划路径；实际下载时可能因去重而调整。
        item_listed 逐条推送：支持流式的 batch 提取器通过显式 on_item 回调在
        每个视频解析完成时交出分集，提取结束后按 identity 或完整 canonical
        snapshot 逐次消费已推送 occurrence，再补发剩余条目；等值但独立的
        occurrence 不会被合并，返回列表始终保持提取器的原始顺序。
        """
        streamed_by_identity: dict[int, _StreamedResolvedItem] = {}
        streamed_by_item: dict[ResolvedItem, deque[_StreamedResolvedItem]] = {}

        async def stream_episode(episode: ResolvableEpisode) -> None:
            streamed = streamed_by_identity.get(id(episode))
            # identity 只用于防御同一 occurrence 的重复 callback；强引用 episode
            # 可避免本次 resolve 内 id 重用。等值但不同对象仍分别创建 snapshot。
            if streamed is not None and streamed.episode is episode:
                await asyncio.sleep(0)
                return
            item = episode.info["listing"]
            streamed = _StreamedResolvedItem(episode=episode, item=item)
            streamed_by_identity[id(episode)] = streamed
            streamed_by_item.setdefault(item, deque()).append(streamed)
            _emit_item_listed(item)
            await asyncio.sleep(0)

        outcome = await self.resolve_request(scope, request, on_item=stream_episode)
        items: list[ResolvedItem] = []
        for episode in outcome.items:
            streamed = streamed_by_identity.get(id(episode))
            if streamed is not None and streamed.episode is episode and not streamed.consumed:
                streamed.consumed = True
                item = streamed.item
            else:
                probe = episode.info["listing"]
                pending = streamed_by_item.get(probe)
                while pending and pending[0].consumed:
                    pending.popleft()
                if pending:
                    streamed = pending.popleft()
                    streamed.consumed = True
                    item = streamed.item
                else:
                    item = probe
                    _emit_item_listed(item)
                    # 未流式化的提取器仍会在这个无 await 的循环里整批产出 item_listed；
                    # 逐条让出控制权给事件消费者（如 server 每连接的 sender），
                    # 避免超出其发送队列容量触发 slow-consumer 断连
                    await asyncio.sleep(0)
            items.append(item)
        return _ResolvedItemsOutcome(items=tuple(items), failures=outcome.failures)

    async def process_request(
        self,
        scope: ExecutionScope,
        request: DownloadRequest,
    ) -> tuple[ItemResult, ...]:
        outcome = await self.resolve_request(scope, request)
        download_list = outcome.items

        prepared: list[tuple[ResolvableEpisode, Path, str | None]] = []
        current_display_group: str | None = None
        for episode in download_list:
            path = Path(self.unique_path(str(episode.info["path"])))
            prepared.append((episode, path, current_display_group))
            current_display_group = episode.info["listing"].display_group

        if request.network.download_interval > 0 and len(prepared) > 1:
            emit_download_report(f"下载任务启动间隔 {request.network.download_interval} 秒")

        results: list[ItemResult | None] = [None] * len(prepared)
        start_turns = [asyncio.Event() for _ in prepared]
        if start_turns:
            start_turns[0].set()

        async def run_item(
            index: int,
            episode: ResolvableEpisode,
            path: Path,
            previous_display_group: str | None,
        ) -> None:
            if index > 0 and request.network.download_interval > 0:
                await asyncio.sleep(index * request.network.download_interval)
            await start_turns[index].wait()
            async with self._item_limiter:
                # 中途校验基于请求级缓存的用户信息（见 get_user_info），不会重复请求；
                # 凭据若在过程中失效，需等当前 ExecutionScope 关闭后才能被发现
                if not await validate_user_info(
                    scope,
                    {"is_login": request.access.login_strict, "vip_status": request.access.vip_strict},
                ):
                    raise NotLoginError("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")
                episode_data = await episode.resolve_data()
                if episode_data is None:
                    if index + 1 < len(start_turns):
                        start_turns[index + 1].set()
                    return
                episode_data = ensure_unique_path(episode_data, lambda _path: str(path))
                if request.output.enforce_directory_boundary:
                    ensure_output_path_is_scoped(
                        episode_data["info"]["path"],
                        request.output.directory,
                        request.output.temporary_directory or request.output.directory,
                    )
                if request.scope.batch:
                    display_info: EpisodeInfo = {
                        "listing": episode.info["listing"],
                        "path": path,
                    }
                    show_batch_episode_title(
                        display_info,
                        index + 1,
                        len(download_list),
                        previous_display_group,
                    )
                # Event.set() 不会让出控制权，因此本任务会先进入 process_download、
                # 输出“开始处理视频”，再在首次 await 时让下一条按序启动。
                if index + 1 < len(start_turns):
                    start_turns[index + 1].set()
                results[index] = await process_download(
                    scope,
                    episode_data,
                    request,
                    path_leases=self.path_leases,
                )

        tasks = [
            asyncio.create_task(
                run_item(index, episode, path, previous_display_group),
                name=f"yutto-item-{index}",
            )
            for index, (episode, path, previous_display_group) in enumerate(prepared)
        ]
        await _gather_cancelling(tasks)
        emit_download_report("", ReportLevel.PLAIN)
        return tuple(result for result in results if result is not None)

    async def resolve_request(
        self,
        scope: ExecutionScope,
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
            scope,
            {"is_login": request.access.login_strict, "vip_status": request.access.vip_strict},
        ):
            raise NotLoginError("启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！")
        # 重定向到可识别的 url
        try:
            url = unwrap_fetch_result(await Fetcher.get_redirected_url(scope, url))
        except InvalidUrlError:
            raise WrongUrlError(f"无效的 url({url})～请检查一下链接是否正确～") from None
        except UnsupportedProtocolError:
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
                if isinstance(extractor, BatchExtractor):
                    download_list = await extractor(scope, extractor_options, on_item=on_item)
                else:
                    download_list = await extractor(scope, extractor_options)
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
        emit_download_report(f"文件名重复，已重命名为 {new_path.name}", ReportLevel.WARNING)
    return episode_data


def ensure_output_path_is_scoped(path: Path, output_root: Path, temporary_root: Path) -> None:
    # anchor 检查覆盖 Windows 上 is_absolute() 为 False 的盘符相对/根路径（如 "/x"、"C:x"）
    if path.is_absolute() or path.anchor or ".." in path.parts:
        raise WrongArgumentError("解析后的输出路径超出了 server 配置的根目录")
    for root in (output_root.resolve(), temporary_root.resolve()):
        if not (root / path).resolve().is_relative_to(root):
            raise WrongArgumentError("解析后的输出路径超出了 server 配置的根目录")


async def _gather_cancelling(tasks: Sequence[asyncio.Task[None]]) -> None:
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
