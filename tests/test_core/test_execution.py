from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from yutto.core.execution import ExecutionScope, RequestExecutionScopeFactory
from yutto.core.request import DownloadRequest
from yutto.types import UserInfo
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


def make_request() -> DownloadRequest:
    return DownloadRequest.model_validate({"source": {"url": "BV1scope"}})


@pytest.mark.parametrize(
    ("fetch_workers", "download_workers", "field"),
    [
        (0, 8, "fetch_workers"),
        (8, 0, "download_workers"),
    ],
)
def test_execution_scope_rejects_non_positive_workers(
    fetch_workers: int,
    download_workers: int,
    field: str,
):
    with pytest.raises(ValueError, match=rf"{field} must be at least 1"):
        ExecutionScope(
            cast("Any", object()),
            fetch_workers=fetch_workers,
            download_workers=download_workers,
        )


@as_sync
async def test_execution_scope_download_guard_limits_concurrency():
    scope = ExecutionScope(cast("Any", object()), download_workers=2)
    running = 0
    max_running = 0

    async def work() -> None:
        nonlocal running, max_running
        async with scope.download_guard():
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(*(work() for _ in range(8)))

    assert max_running == 2


@as_sync
async def test_scope_factory_opens_fresh_clients_limiters_and_caches():
    factory = RequestExecutionScopeFactory()
    request = make_request()

    async with factory.open(request) as first_scope:
        first_client = first_scope.client
        first_fetch_limiter = first_scope.fetch_limiter
        first_download_limiter = first_scope.download_limiter
        first_scope.user_info_cache = UserInfo(vip_status=True, is_login=True)
        first_scope.wbi_img_cache = {"img_key": "img", "sub_key": "sub"}
        first_scope.touched_urls.add("https://example.com")

    assert first_client.is_closed

    async with factory.open(request) as second_scope:
        assert second_scope.client is not first_client
        assert second_scope.fetch_limiter is not first_fetch_limiter
        assert second_scope.download_limiter is not first_download_limiter
        assert second_scope.user_info_cache is None
        assert second_scope.wbi_img_cache is None
        assert second_scope.touched_urls == set()


@as_sync
async def test_scope_factory_closes_client_when_on_open_fails():
    clients: list[Any] = []

    async def fail_on_open(scope: ExecutionScope, request: DownloadRequest) -> None:
        clients.append(scope.client)
        raise RuntimeError("on_open failed")

    factory = RequestExecutionScopeFactory(on_open=fail_on_open)

    with pytest.raises(RuntimeError, match="on_open failed"):
        async with factory.open(make_request()):
            pytest.fail("scope should not be yielded")

    assert len(clients) == 1
    assert clients[0].is_closed
