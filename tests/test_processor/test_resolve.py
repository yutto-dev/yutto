from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from returns.result import Success

import yutto.download_manager as download_manager_module
from yutto.core.events import DownloadItemListed, DownloadStage, DownloadStageChanged
from yutto.core.operation import bind_download_event_sink
from yutto.core.request import DownloadRequest
from yutto.core.result import ResolvedItem, ResolveResult
from yutto.download_manager import DownloadManager, ResolveFailedError
from yutto.types import AId, CId, ResolvableEpisode
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.fetcher import Fetcher, FetcherContext
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

    data_coro = resolve_episode()
    info = make_info("P1", display_group="标题")
    resolvable = ResolvableEpisode(info=info, data_coro=CoroutineWrapper(data_coro))

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
    # data 懒协程从未执行，且已被关闭，不会留下 un-awaited 警告
    assert executed == []
    assert inspect.getcoroutinestate(data_coro) == inspect.CORO_CLOSED
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


class _FakeClientContext:
    async def __aenter__(self) -> httpx.AsyncClient:
        return cast("httpx.AsyncClient", object())

    async def __aexit__(self, *args: object) -> bool:
        return False


def _patch_resolve_environment(monkeypatch: pytest.MonkeyPatch, extractor: type) -> None:
    async def fake_validate_user_info(ctx: FetcherContext, requirements: dict[str, bool]) -> bool:
        return True

    async def fake_get_redirected_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(url)

    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", extractor)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)
    monkeypatch.setattr(download_manager_module, "create_client", lambda **_: _FakeClientContext())


class _ShortcutExtractorBase:
    def resolve_shortcut(self, url: str) -> tuple[bool, str]:
        return True, f"https://example.com/{url}"

    def match(self, url: str) -> bool:
        return True


@as_sync
async def test_execute_resolve_fails_when_no_entry_resolves(monkeypatch: pytest.MonkeyPatch):
    class AllFailedExtractor(_ShortcutExtractorBase):
        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ) -> list[ResolvableEpisode | None]:
            # extractor 用 None 同时表达「解析失败」与「被过滤」（视频不存在 / 无权限 / 请求失败）
            return [None, None]

    _patch_resolve_environment(monkeypatch, AllFailedExtractor)
    manager = DownloadManager()
    request = DownloadRequest.model_validate({"source": {"url": "BV1failed"}})

    # 「来源存在条目但全部未解析成功」不能伪装成一次成功的空结果
    with bind_download_event_sink(RecordingEventSink()), pytest.raises(ResolveFailedError):
        await manager.execute_resolve(FetcherContext(), [request])


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
