from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest
from returns.result import Failure, Success

from yutto.core.execution import ExecutionScope
from yutto.exceptions import MaxRetryError, NotFoundError
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.types import AId
from yutto.utils.fetcher import Fetcher
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx
    from returns.result import Result

    from yutto.api.ugc_video import UgcVideoList
    from yutto.types import AvId


def make_ugc_video_list(avid: AvId, pubdate: int = 1_600_000_000) -> UgcVideoList:
    return {
        "title": f"video-{avid}",
        "avid": avid,
        "pubdate": pubdate,
        "pages": [],
    }


def make_fake_client() -> httpx.AsyncClient:
    return cast("httpx.AsyncClient", object())


async def touch_url_ok(scope: ExecutionScope, url: str) -> Result[None, MaxRetryError]:
    return Success(None)


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_preserves_order(monkeypatch: pytest.MonkeyPatch):
    avids: list[AvId] = [AId("1"), AId("2"), AId("3"), AId("4"), AId("5")]
    filtered_avid = avids[2]

    async def fake_get_ugc_video_list(scope: ExecutionScope, avid: AvId) -> UgcVideoList:
        # 让完成顺序与传入顺序相反，验证结果顺序不受完成顺序影响
        await asyncio.sleep(0.01 * (len(avids) - avids.index(avid)))
        if avid == filtered_avid:
            # 早于默认过滤窗口起点（1971 年），会被发布时间过滤器过滤
            return make_ugc_video_list(avid, pubdate=0)
        return make_ugc_video_list(avid)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", touch_url_ok)

    scope = ExecutionScope(make_fake_client())
    outcome = await resolve_ugc_video_lists(
        scope,
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert [item.value["title"] for item in outcome.items] == [
        "video-1",
        "video-2",
        "video-4",
        "video-5",
    ]
    assert [item.index for item in outcome.items] == [0, 1, 3, 4]
    assert outcome.failures == ()


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_isolates_failures(monkeypatch: pytest.MonkeyPatch):
    avids: list[AvId] = [AId("1"), AId("2"), AId("3"), AId("4")]
    not_found_avid = avids[1]
    max_retry_url = avids[2].to_url()

    async def fake_get_ugc_video_list(scope: ExecutionScope, avid: AvId) -> UgcVideoList:
        if avid == not_found_avid:
            raise NotFoundError(f"啊叻？视频 {avid} 不见了诶")
        return make_ugc_video_list(avid)

    async def fake_touch_url(scope: ExecutionScope, url: str) -> Result[None, MaxRetryError]:
        # 走真实的 unwrap_fetch_result 抛出路径
        if url == max_retry_url:
            return Failure(MaxRetryError("超出最大重试次数！"))
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    scope = ExecutionScope(make_fake_client())
    outcome = await resolve_ugc_video_lists(
        scope,
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert [item.index for item in outcome.items] == [0, 3]
    assert [str(item.source) for item in outcome.items] == ["1", "4"]
    assert [failure.index for failure in outcome.failures] == [1, 2]
    assert [str(failure.source) for failure in outcome.failures] == ["2", "3"]
    assert [type(failure.error).__name__ for failure in outcome.failures] == ["NotFoundError", "MaxRetryError"]


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_bounded_by_fetch_semaphore(monkeypatch: pytest.MonkeyPatch):
    fetch_workers = 2
    running = 0
    max_running = 0

    scope = ExecutionScope(make_fake_client(), fetch_workers=fetch_workers)

    async def occupy_fetch_guard(active_scope: ExecutionScope) -> None:
        nonlocal running, max_running
        # 模拟真实 Fetcher 请求经过 scope.fetch_guard() 的行为
        async with active_scope.fetch_guard():
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1

    async def fake_get_ugc_video_list(active_scope: ExecutionScope, avid: AvId) -> UgcVideoList:
        await occupy_fetch_guard(active_scope)
        return make_ugc_video_list(avid)

    async def fake_touch_url(active_scope: ExecutionScope, url: str) -> Result[None, MaxRetryError]:
        # touch_url 与其他请求共用同一个 fetch semaphore，也计入并发统计
        await occupy_fetch_guard(active_scope)
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    avids: list[AvId] = [AId(str(i)) for i in range(10)]
    outcome = await resolve_ugc_video_lists(
        scope,
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert len(outcome.items) == len(avids)
    assert outcome.failures == ()
    assert max_running == fetch_workers
