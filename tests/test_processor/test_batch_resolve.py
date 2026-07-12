from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest
from returns.result import Failure, Success

from yutto.exceptions import MaxRetryError, NotFoundError
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.types import AId
from yutto.utils.fetcher import Fetcher, FetcherContext
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


async def touch_url_ok(ctx: FetcherContext, client: httpx.AsyncClient, url: str) -> Result[None, MaxRetryError]:
    return Success(None)


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_preserves_order(monkeypatch: pytest.MonkeyPatch):
    avids: list[AvId] = [AId("1"), AId("2"), AId("3"), AId("4"), AId("5")]
    filtered_avid = avids[2]

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: AvId) -> UgcVideoList:
        # 让完成顺序与传入顺序相反，验证结果顺序不受完成顺序影响
        await asyncio.sleep(0.01 * (len(avids) - avids.index(avid)))
        if avid == filtered_avid:
            # 早于默认过滤窗口起点（1971 年），会被发布时间过滤器过滤
            return make_ugc_video_list(avid, pubdate=0)
        return make_ugc_video_list(avid)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", touch_url_ok)

    results = await resolve_ugc_video_lists(
        FetcherContext(),
        make_fake_client(),
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert [result["title"] if result is not None else None for result in results] == [
        "video-1",
        "video-2",
        None,
        "video-4",
        "video-5",
    ]


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_isolates_failures(monkeypatch: pytest.MonkeyPatch):
    avids: list[AvId] = [AId("1"), AId("2"), AId("3"), AId("4")]
    not_found_avid = avids[1]
    max_retry_url = avids[2].to_url()

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: AvId) -> UgcVideoList:
        if avid == not_found_avid:
            raise NotFoundError(f"啊叻？视频 {avid} 不见了诶")
        return make_ugc_video_list(avid)

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str) -> Result[None, MaxRetryError]:
        # 走真实的 unwrap_fetch_result 抛出路径
        if url == max_retry_url:
            return Failure(MaxRetryError("超出最大重试次数！"))
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    results = await resolve_ugc_video_lists(
        FetcherContext(),
        make_fake_client(),
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert results[0] is not None
    assert results[1] is None
    assert results[2] is None
    assert results[3] is not None


@pytest.mark.processor
@as_sync
async def test_resolve_ugc_video_lists_bounded_by_fetch_semaphore(monkeypatch: pytest.MonkeyPatch):
    fetch_workers = 2
    running = 0
    max_running = 0

    ctx = FetcherContext()
    ctx.set_fetch_semaphore(fetch_workers=fetch_workers)

    async def occupy_fetch_guard() -> None:
        nonlocal running, max_running
        # 模拟真实 Fetcher 请求经过 ctx.fetch_guard() 的行为
        async with ctx.fetch_guard():
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1

    async def fake_get_ugc_video_list(ctx: FetcherContext, client: httpx.AsyncClient, avid: AvId) -> UgcVideoList:
        await occupy_fetch_guard()
        return make_ugc_video_list(avid)

    async def fake_touch_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str) -> Result[None, MaxRetryError]:
        # touch_url 与其他请求共用同一个 fetch semaphore，也计入并发统计
        await occupy_fetch_guard()
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)

    avids: list[AvId] = [AId(str(i)) for i in range(10)]
    results = await resolve_ugc_video_lists(
        ctx,
        make_fake_client(),
        avids,
        publication_time_filter=PublicationTimeFilter.from_strings(),
    )

    assert all(result is not None for result in results)
    assert max_running == fetch_workers
