from __future__ import annotations

import asyncio

import pytest

from tests.helpers.http_range_server import LocalRangeServer
from yutto._native import (
    HttpStatusError,
    InvalidUrlError,
    SessionClosedError,
    UnsupportedProtocolError,
    YuttoSession,
    wait_for_transfer,
)
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


@as_sync
async def test_yutto_session_get_exposes_response_and_typed_errors():
    with LocalRangeServer(b"payload") as server:
        session = YuttoSession(use_system_proxy=False)
        response = await session.get(server.url, params=[("query", "a b")])
        missing = await session.get(server.url, headers={"Range": "bytes=99-100"})

    assert response.status_code == 200
    assert response.is_success
    assert response.body == b"payload"
    assert response.url.endswith("/media?query=a+b")
    assert response.header("etag") is not None
    assert response.header("missing") is None
    response.raise_for_status()
    assert missing.status_code == 416
    with pytest.raises(HttpStatusError, match="HTTP status 416"):
        missing.raise_for_status()
    with pytest.raises(InvalidUrlError):
        await session.get("not a URL")
    with pytest.raises(UnsupportedProtocolError):
        await session.get("ftp://example.com/resource")


@as_sync
async def test_yutto_session_close_is_idempotent_and_rejects_new_work(tmp_path):
    session = YuttoSession(use_system_proxy=False)

    session.close()
    session.close()

    assert session.is_closed
    with pytest.raises(SessionClosedError):
        await session.get("https://example.com")
    with pytest.raises(SessionClosedError):
        session.start_transfer(["https://example.com/media"], tmp_path / "media", 1)


@as_sync
async def test_yutto_session_get_propagates_asyncio_cancellation():
    payload = b"payload"
    with LocalRangeServer(payload, delays={(0, len(payload) - 1): 0.2}) as server:
        session = YuttoSession(use_system_proxy=False)
        future = asyncio.ensure_future(session.get(server.url, headers={"Range": f"bytes=0-{len(payload) - 1}"}))
        while not server.requests:
            await asyncio.sleep(0)
        future.cancel()
        with pytest.raises(asyncio.CancelledError):
            await future


@as_sync
async def test_yutto_session_starts_a_transfer_with_its_client(tmp_path):
    payload = b"native transfer"
    target = tmp_path / "media"

    with LocalRangeServer(payload) as server:
        session = YuttoSession(use_system_proxy=False)
        handle = session.start_transfer([server.url], target, len(payload), overwrite=True)
        committed = await wait_for_transfer(handle, poll_interval=0)

    assert committed == len(payload)
    assert target.read_bytes() == payload
