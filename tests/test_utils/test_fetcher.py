from __future__ import annotations

import asyncio
import ssl
from typing import Any, Protocol, cast

import httpx
import pytest
from returns.result import Failure, Success

from yutto.utils.fetcher import Fetcher, FetcherContext, create_client, create_sync_client, resolve_proxy
from yutto.utils.functional import as_sync


class _HasSSLContext(Protocol):
    _ssl_context: ssl.SSLContext


class _HasPool(Protocol):
    _pool: _HasSSLContext


def _transport_ssl_context(transport: Any) -> ssl.SSLContext:
    # Test helper: inspect httpx's private transport internals to assert TLS policy wiring.
    # If httpx changes `_pool._ssl_context`, this assertion helper will need to be updated too.
    return cast("_HasPool", transport)._pool._ssl_context


def test_resolve_proxy_auto_uses_system_proxy():
    assert resolve_proxy("auto") == (None, True)


def test_resolve_proxy_supports_socks5():
    assert resolve_proxy("socks5://127.0.0.1:1080") == ("socks5://127.0.0.1:1080", False)


def test_fetcher_context_set_proxy_reuses_shared_rules():
    ctx = FetcherContext()

    ctx.set_proxy("https://127.0.0.1:7890")

    assert ctx.proxy == "https://127.0.0.1:7890"
    assert not ctx.trust_env


def test_resolve_proxy_rejects_invalid_scheme():
    with pytest.raises(ValueError, match="proxy 参数值"):
        resolve_proxy("ftp://127.0.0.1:21")


def test_create_client_keeps_download_tls_verification_disabled():
    client = create_client()
    try:
        transport: Any = client._transport
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert not ssl_context.check_hostname
    finally:
        asyncio.run(client.aclose())


def test_create_sync_client_follows_default_download_tls_policy():
    client = create_sync_client()
    try:
        transport: Any = client._transport
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert not ssl_context.check_hostname
    finally:
        client.close()


def test_create_sync_client_can_enable_tls_verification():
    client = create_sync_client(verify=True)
    try:
        transport: Any = client._transport
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname
    finally:
        client.close()


class _StatusClient:
    def __init__(self, status_code: int):
        self.status_code = status_code

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(self.status_code, request=httpx.Request("GET", url), content=b"failed")


@as_sync
async def test_fetch_bin_keeps_non_success_status_as_success_none():
    match await Fetcher.fetch_bin(FetcherContext(), cast("Any", _StatusClient(404)), "https://example.com"):
        case Success(None):
            pass
        case result:
            pytest.fail(f"expected Success(None), got {result}")


@as_sync
async def test_fetch_json_retries_non_success_status():
    match await Fetcher.fetch_json(FetcherContext(), cast("Any", _StatusClient(404)), "https://example.com"):
        case Failure(error):
            assert error.message == "超出最大重试次数！"
        case result:
            pytest.fail(f"expected Failure, got {result}")


@as_sync
async def test_get_redirected_url_keeps_non_success_status_as_url():
    match await Fetcher.get_redirected_url(FetcherContext(), cast("Any", _StatusClient(404)), "https://example.com"):
        case Success(url):
            assert url == "https://example.com"
        case result:
            pytest.fail(f"expected Success, got {result}")


@as_sync
async def test_touch_url_keeps_non_success_status_as_success_none():
    match await Fetcher.touch_url(FetcherContext(), cast("Any", _StatusClient(404)), "https://example.com"):
        case Success(None):
            pass
        case result:
            pytest.fail(f"expected Success(None), got {result}")


@pytest.mark.processor
@as_sync
async def test_touch_url_cache_is_scoped_to_context_and_client():
    class CountingClient(_StatusClient):
        def __init__(self):
            super().__init__(204)
            self.calls = 0

        async def get(self, url: str, **kwargs: Any) -> httpx.Response:
            self.calls += 1
            return await super().get(url, **kwargs)

    first_client = CountingClient()
    second_client = CountingClient()
    first_context = FetcherContext()
    second_context = FetcherContext()

    assert isinstance(await Fetcher.touch_url(first_context, cast("Any", first_client), "https://example.com"), Success)
    assert isinstance(await Fetcher.touch_url(first_context, cast("Any", first_client), "https://example.com"), Success)
    assert isinstance(
        await Fetcher.touch_url(second_context, cast("Any", first_client), "https://example.com"), Success
    )
    assert isinstance(
        await Fetcher.touch_url(second_context, cast("Any", second_client), "https://example.com"), Success
    )
    assert first_client.calls == 2
    assert second_client.calls == 1
