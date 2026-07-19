from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from returns.result import Success

import yutto.download_manager as download_manager_module
from yutto.core.events import DownloadItemListed, DownloadStage, DownloadStageChanged
from yutto.core.operation import (
    bind_download_event_sink,
    collect_resolve_failures,
    notify_episode_listed,
    report_resolve_failure,
)
from yutto.core.request import DownloadRequest
from yutto.core.result import ResolvedItem, ResolveFailure, ResolveResult
from yutto.download_manager import DownloadManager
from yutto.exceptions import ErrorCode, MaxRetryError, NotFoundError, NotLoginError, ResolveFailedError
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.types import AId, CId, ResolvableEpisode
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx

    from yutto.core.events import DownloadEvent
    from yutto.types import EpisodeData, EpisodeInfo, ExtractorOptions

pytestmark = pytest.mark.processor


def make_info(name: str, display_group: str | None = None) -> EpisodeInfo:
    return {
        "avid": AId("1"),
        "cid": CId("10"),
        "url": "https://www.bilibili.com/video/av1?p=1",
        "name": name,
        "title": "标题",
        "cover_url": "https://example.com/cover.jpg",
        "uploader": "某UP主",
        "description": "视频简介",
        "tags": ["标签A", "标签B"],
        "path": Path(f"标题/{name}"),
        "display_group": display_group,
    }


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[DownloadEvent] = []

    def emit(self, event: DownloadEvent) -> None:
        self.events.append(event)


@as_sync
async def test_resolve_items_lists_stable_info_without_resolving_data(monkeypatch: pytest.MonkeyPatch):
    executed: list[str] = []

    async def resolve_episode() -> EpisodeData | None:
        executed.append("ran")
        return None

    info = make_info("P1", display_group="标题")
    resolvable = ResolvableEpisode(info=info, resolve_data=resolve_episode)

    class FakeExtractor:
        def resolve_shortcut(self, url: str) -> tuple[bool, str]:
            return True, f"https://example.com/{url}"

        def match(self, url: str) -> bool:
            return url == "https://example.com/BV1baseline"

        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            return [None, resolvable]

    async def fake_validate_user_info(ctx: FetcherContext, requirements: dict[str, bool]) -> bool:
        return True

    async def fake_get_redirected_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(url)

    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", FakeExtractor)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)

    manager = DownloadManager()
    sink = RecordingEventSink()
    client = cast("httpx.AsyncClient", object())
    request = DownloadRequest.model_validate({"source": {"url": "BV1baseline"}})

    with bind_download_event_sink(sink):
        items = await manager.resolve_items(client, FetcherContext(), request)

    expected_item = ResolvedItem(
        avid="1",
        cid="10",
        url="https://www.bilibili.com/video/av1?p=1",
        name="P1",
        title="标题",
        cover_url="https://example.com/cover.jpg",
        planned_path=Path("标题/P1"),
        display_group="标题",
        uploader="某UP主",
        description="视频简介",
        tags=("标签A", "标签B"),
    )
    assert items == [expected_item]
    # data resolver 从未调用，因此没有未 await 的 coroutine 需要清理
    assert executed == []
    assert sink.events == [
        DownloadStageChanged(name=DownloadStage.RESOLVING),
        DownloadItemListed(
            avid="1",
            cid="10",
            url="https://www.bilibili.com/video/av1?p=1",
            name="P1",
            title="标题",
            cover_url="https://example.com/cover.jpg",
            planned_path=Path("标题/P1"),
            display_group="标题",
            uploader="某UP主",
            description="视频简介",
            tags=("标签A", "标签B"),
        ),
    ]


@as_sync
async def test_resolve_items_streams_hooked_episodes_without_duplicates(monkeypatch: pytest.MonkeyPatch):
    """流式提取器经 notify_episode_listed 提前推送的条目不会被收尾补发重复。"""

    resolved: list[str] = []

    async def noop() -> EpisodeData | None:
        resolved.append("ran")
        return None

    streamed = ResolvableEpisode(info=make_info("P1", display_group="标题"), resolve_data=noop)
    late = ResolvableEpisode(info=make_info("P2", display_group="标题"), resolve_data=noop)

    class FakeExtractor:
        def resolve_shortcut(self, url: str) -> tuple[bool, str]:
            return True, f"https://example.com/{url}"

        def match(self, url: str) -> bool:
            return url == "https://example.com/BV1stream"

        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            # 流式提取器：解析过程中先推送 P1；P2 留给 resolve_items 收尾补发
            notify_episode_listed(streamed)
            return [streamed, late]

    async def fake_validate_user_info(ctx: FetcherContext, requirements: dict[str, bool]) -> bool:
        return True

    async def fake_get_redirected_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(url)

    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", FakeExtractor)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)

    manager = DownloadManager()
    sink = RecordingEventSink()
    client = cast("httpx.AsyncClient", object())
    request = DownloadRequest.model_validate({"source": {"url": "BV1stream"}})

    with bind_download_event_sink(sink):
        items = await manager.resolve_items(client, FetcherContext(), request)

    listed = [event for event in sink.events if isinstance(event, DownloadItemListed)]
    # 每条恰好一次：流式推送的 P1 在前（提取中），P2 收尾补发
    assert [event.name for event in listed] == ["P1", "P2"]
    # 返回列表保持提取器给出的顺序
    assert [item.name for item in items] == ["P1", "P2"]
    # resolve-only 路径不会调用 data resolver，也不会提前创建 coroutine
    assert resolved == []


class _FakeClientContext:
    async def __aenter__(self) -> httpx.AsyncClient:
        return cast("httpx.AsyncClient", object())

    async def __aexit__(self, *args: object) -> bool:
        return False


def _patch_resolve_network(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_validate_user_info(ctx: FetcherContext, requirements: dict[str, bool]) -> bool:
        return True

    async def fake_get_redirected_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(url)

    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)
    monkeypatch.setattr(download_manager_module, "create_client", lambda **_: _FakeClientContext())


def _patch_resolve_environment(monkeypatch: pytest.MonkeyPatch, extractor: type) -> None:
    _patch_resolve_network(monkeypatch)
    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", extractor)


class _ShortcutExtractorBase:
    def resolve_shortcut(self, url: str) -> tuple[bool, str]:
        return True, f"https://example.com/{url}"

    def match(self, url: str) -> bool:
        return True


@as_sync
async def test_execute_resolve_treats_filtered_only_nones_as_empty_success(monkeypatch: pytest.MonkeyPatch):
    class FilteredExtractor(_ShortcutExtractorBase):
        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            # 纯过滤（如发布时间过滤 / 选集过滤）产生的 None：没有失败上报
            return [None, None]

    _patch_resolve_environment(monkeypatch, FilteredExtractor)
    manager = DownloadManager()
    request = DownloadRequest.model_validate({"source": {"url": "BV1filtered"}})

    with bind_download_event_sink(RecordingEventSink()):
        result = await manager.execute_resolve(FetcherContext(), [request])

    assert result == ResolveResult(items=(), failures=())


@as_sync
async def test_execute_resolve_raises_original_error_when_batch_source_is_gone(monkeypatch: pytest.MonkeyPatch):
    async def raise_not_found(ctx: FetcherContext, client: httpx.AsyncClient, avid: object):
        raise NotFoundError(f"啊叻？视频 {avid} 不见了诶")

    _patch_resolve_network(monkeypatch)
    monkeypatch.setattr("yutto.extractor.ugc_video_batch.get_ugc_video_list", raise_not_found)
    manager = DownloadManager()
    request = DownloadRequest.model_validate(
        {"source": {"url": "https://www.bilibili.com/video/BV1AbCdEfGhI"}, "scope": {"batch": True}}
    )

    # 真实 UgcVideoBatchExtractor 错误路径：NotFoundError 被吞成 [] 后不再伪装成空成功，
    # 任务以原始异常失败，wire 错误码是稳定的 NOT_FOUND_ERROR 而非 internal_error
    with bind_download_event_sink(RecordingEventSink()), pytest.raises(NotFoundError) as error_info:
        await manager.execute_resolve(FetcherContext(), [request])
    assert error_info.value.code is ErrorCode.NOT_FOUND_ERROR


@as_sync
async def test_execute_resolve_raises_original_error_when_watch_later_needs_login(monkeypatch: pytest.MonkeyPatch):
    async def raise_not_login(ctx: FetcherContext, client: httpx.AsyncClient):
        raise NotLoginError("账号未登录，无法获取稍后再看列表")

    _patch_resolve_network(monkeypatch)
    monkeypatch.setattr("yutto.extractor.user_watch_later.get_watch_later_avids", raise_not_login)
    manager = DownloadManager()
    request = DownloadRequest.model_validate(
        {"source": {"url": "https://www.bilibili.com/watchlater/"}, "scope": {"batch": True}}
    )

    # 真实 UserWatchLaterExtractor 错误路径：未登录时不再以空成功掩盖 NotLoginError
    with bind_download_event_sink(RecordingEventSink()), pytest.raises(NotLoginError) as error_info:
        await manager.execute_resolve(FetcherContext(), [request])
    assert error_info.value.code is ErrorCode.NOT_LOGIN_ERROR


@as_sync
async def test_execute_resolve_reports_partial_failures(monkeypatch: pytest.MonkeyPatch):
    async def resolve_episode() -> EpisodeData | None:
        return None

    resolvable = ResolvableEpisode(info=make_info("P1"), resolve_data=resolve_episode)

    class PartialExtractor(_ShortcutExtractorBase):
        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            report_resolve_failure(MaxRetryError("获取视频 av2 信息失败：超出最大重试次数！"))
            return [resolvable, None]

    _patch_resolve_environment(monkeypatch, PartialExtractor)
    manager = DownloadManager()
    request = DownloadRequest.model_validate({"source": {"url": "BV1partial"}})

    with bind_download_event_sink(RecordingEventSink()):
        result = await manager.execute_resolve(FetcherContext(), [request])

    # 部分失败：成功条目照常返回，失败以结构化形式保留在 failures 中
    assert len(result.items) == 1
    assert result.failures == (
        ResolveFailure(
            type="MaxRetryError",
            message="获取视频 av2 信息失败：超出最大重试次数！",
            code=ErrorCode.MAX_RETRY_ERROR.value,
        ),
    )


@as_sync
async def test_execute_resolve_aggregates_multiple_failures(monkeypatch: pytest.MonkeyPatch):
    class AllFailedExtractor(_ShortcutExtractorBase):
        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            report_resolve_failure(NotFoundError("啊叻？视频 av1 不见了诶"))
            report_resolve_failure(MaxRetryError("获取视频 av2 信息失败：超出最大重试次数！"))
            return [None, None]

    _patch_resolve_environment(monkeypatch, AllFailedExtractor)
    manager = DownloadManager()
    request = DownloadRequest.model_validate({"source": {"url": "BV1failed"}})

    with bind_download_event_sink(RecordingEventSink()), pytest.raises(ResolveFailedError) as error_info:
        await manager.execute_resolve(FetcherContext(), [request])
    assert error_info.value.code is ErrorCode.RESOLVE_FAILED_ERROR


@as_sync
async def test_resolve_ugc_video_lists_reports_expected_failures(monkeypatch: pytest.MonkeyPatch):
    # pubdate 需落在默认过滤窗口（1971-01-01 起）内，用一个正常的时间戳
    fake_list = {"title": "视频 2", "pubdate": 1700000000, "avid": AId("2"), "pages": []}

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: object):
        if str(avid) == "1":
            raise MaxRetryError("超出最大重试次数！")
        return fake_list

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    client = cast("httpx.AsyncClient", object())
    with collect_resolve_failures() as failures:
        results = await resolve_ugc_video_lists(
            FetcherContext(),
            client,
            [AId("1"), AId("2")],
            publication_time_filter=PublicationTimeFilter.from_strings(None, None),
        )

    # 失败以 None 占位、顺序保持，同时结构化上报 —— 收藏夹等批量 extractor 丢弃 None 前信息不再丢失
    assert results == [None, fake_list]
    assert [type(error).__name__ for error in failures] == ["MaxRetryError"]


@as_sync
async def test_resolve_ugc_video_lists_awaits_async_on_resolved(monkeypatch: pytest.MonkeyPatch):
    fake_list = {"title": "视频", "pubdate": 1700000000, "avid": AId("2"), "pages": []}

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: object):
        return fake_list

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    calls: list[tuple[int, str, bool]] = []

    async def on_resolved(index: int, avid: object, result: object) -> None:
        calls.append((index, str(avid), result is not None))
        # 契约：回调是异步的，逐分集的让出由回调自身负责（内置提取器均如此）
        await asyncio.sleep(0)

    client = cast("httpx.AsyncClient", object())
    results = await resolve_ugc_video_lists(
        FetcherContext(),
        client,
        [AId("1"), AId("2")],
        publication_time_filter=PublicationTimeFilter.from_strings(None, None),
        on_resolved=on_resolved,
    )

    # 每个视频恰好触发一次 await 回调，携带 (入参序 index, avid, 解析结果)
    assert len(results) == 2
    assert sorted(calls) == [(0, "1", True), (1, "2", True)]


@as_sync
async def test_resolve_ugc_video_lists_cancels_siblings_on_fatal_error(monkeypatch: pytest.MonkeyPatch):
    first_started = asyncio.Event()

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: object):
        if str(avid) == "1":
            first_started.set()
            await asyncio.sleep(0.05)
            return {"title": "视频 1", "pubdate": 1700000000, "avid": AId("1"), "pages": []}
        raise RuntimeError("boom")

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    calls: list[int] = []

    async def on_resolved(index: int, avid: object, result: object) -> None:
        calls.append(index)

    client = cast("httpx.AsyncClient", object())
    # 单个未预期异常直接抛原始异常（而非 ExceptionGroup），wire 错误类型保持稳定
    with pytest.raises(RuntimeError, match="boom"):
        await resolve_ugc_video_lists(
            FetcherContext(),
            client,
            [AId("1"), AId("2")],
            publication_time_filter=PublicationTimeFilter.from_strings(None, None),
            on_resolved=on_resolved,
        )

    # fatal error 会取消并等待兄弟协程：函数抛错后不会再有任何回调发生
    assert first_started.is_set()
    assert calls == []
    await asyncio.sleep(0.1)
    assert calls == []


@as_sync
async def test_resolve_ugc_video_lists_cancels_workers_when_callback_fails(monkeypatch: pytest.MonkeyPatch):
    resolved: list[str] = []

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: object):
        if str(avid) == "2":
            await asyncio.sleep(0.05)
        resolved.append(str(avid))
        return {"title": str(avid), "pubdate": 1700000000, "avid": avid, "pages": []}

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    async def on_resolved(index: int, avid: object, result: object) -> None:
        raise RuntimeError("callback boom")

    client = cast("httpx.AsyncClient", object())
    with pytest.raises(RuntimeError, match="callback boom"):
        await resolve_ugc_video_lists(
            FetcherContext(),
            client,
            [AId("1"), AId("2")],
            publication_time_filter=PublicationTimeFilter.from_strings(None, None),
            on_resolved=on_resolved,
        )

    # 回调自身失败同样取消其余 worker：慢的 avid 2 不会再完成解析
    assert resolved == ["1"]
    await asyncio.sleep(0.1)
    assert resolved == ["1"]


@as_sync
async def test_execute_resolve_keeps_genuinely_empty_source_as_success(monkeypatch: pytest.MonkeyPatch):
    class EmptySourceExtractor(_ShortcutExtractorBase):
        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            return []

    _patch_resolve_environment(monkeypatch, EmptySourceExtractor)
    manager = DownloadManager()
    request = DownloadRequest.model_validate({"source": {"url": "BV1empty"}})

    with bind_download_event_sink(RecordingEventSink()):
        result = await manager.execute_resolve(FetcherContext(), [request])

    # 真正的空来源（如空收藏夹）仍是成功的空结果，与「全部解析失败」区分开
    assert result == ResolveResult(items=())
