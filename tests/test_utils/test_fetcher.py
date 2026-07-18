from __future__ import annotations

import asyncio
import ssl
from typing import Any, Protocol, cast

import httpx
import pytest
from returns.result import Failure, Success

from yutto.utils.fetcher import (
    Fetcher,
    FetcherContext,
    MaxRetry,
    create_client,
    create_sync_client,
    describe_effective_proxy,
    resolve_proxy,
    sanitize_proxy_url,
)
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
            assert error.message == "超出最大重试次数！（最后错误：HTTPStatusError）"
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


_PROXY_ENV_NAMES = (
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "all_proxy",
    "https_proxy",
    "http_proxy",
    "no_proxy",
)


def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _PROXY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_describe_effective_proxy_prefers_explicit_proxy(monkeypatch: pytest.MonkeyPatch):
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1080")
    assert describe_effective_proxy("http://10.0.0.1:8080", True) == "http://10.0.0.1:8080"


def test_describe_effective_proxy_names_the_env_variable(monkeypatch: pytest.MonkeyPatch):
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:3067")
    assert describe_effective_proxy(None, True) == "HTTPS 请求 → http://127.0.0.1:3067（来自环境变量 HTTPS_PROXY）"


def test_describe_effective_proxy_ignores_env_without_trust_env(monkeypatch: pytest.MonkeyPatch):
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:3067")
    assert describe_effective_proxy(None, False) is None
    assert describe_effective_proxy(None, True) is not None


def test_describe_effective_proxy_without_any_proxy(monkeypatch: pytest.MonkeyPatch):
    _clear_proxy_env(monkeypatch)
    assert describe_effective_proxy(None, True) is None


def test_describe_effective_proxy_masks_credentials():
    # 显式代理与环境代理的 userinfo 都不能进入描述（进而不能进入日志与去重 key）
    assert describe_effective_proxy("http://user:secret@10.0.0.1:8080", True) == "http://10.0.0.1:8080"
    description = describe_effective_proxy(None, True, environ={"ALL_PROXY": "http://user:secret@127.0.0.1:7890"})
    assert description == "http://127.0.0.1:7890（来自环境变量 ALL_PROXY）"
    assert "secret" not in description and "user" not in description


def test_describe_effective_proxy_scheme_specific_beats_all_proxy():
    # httpx 语义：HTTPS 请求优先用 HTTPS_PROXY，ALL_PROXY 仅兜底其余 scheme
    description = describe_effective_proxy(
        None,
        True,
        environ={"HTTPS_PROXY": "http://10.0.0.2:8080", "ALL_PROXY": "http://10.0.0.3:8080"},
    )
    assert description == (
        "HTTPS 请求 → http://10.0.0.2:8080（来自环境变量 HTTPS_PROXY）；"
        "HTTP 请求 → http://10.0.0.3:8080（来自环境变量 ALL_PROXY）"
    )


def test_describe_effective_proxy_merges_same_proxy_for_both_schemes():
    description = describe_effective_proxy(
        None,
        True,
        environ={"HTTPS_PROXY": "http://127.0.0.1:7890", "HTTP_PROXY": "http://127.0.0.1:7890"},
    )
    assert description == "http://127.0.0.1:7890（来自环境变量 HTTPS_PROXY、HTTP_PROXY）"


def test_describe_effective_proxy_no_proxy_wildcard_disables_env_proxies():
    # httpx 语义：NO_PROXY 含 * 时完全不使用环境代理
    assert describe_effective_proxy(None, True, environ={"ALL_PROXY": "http://127.0.0.1:7890", "NO_PROXY": "*"}) is None


def test_describe_effective_proxy_mentions_no_proxy_exceptions():
    description = describe_effective_proxy(
        None,
        True,
        environ={"ALL_PROXY": "http://127.0.0.1:7890", "NO_PROXY": "localhost,.example.com"},
    )
    assert description == (
        "http://127.0.0.1:7890（来自环境变量 ALL_PROXY）；NO_PROXY=localhost,.example.com 命中的主机将直连"
    )


def test_describe_effective_proxy_lowercase_overrides_uppercase():
    # urllib getproxies_environment 语义：小写变量覆盖大写变量，空值小写变量则移除代理
    description = describe_effective_proxy(
        None,
        True,
        environ={"HTTP_PROXY": "http://10.0.0.4:8080", "http_proxy": "http://10.0.0.5:8080"},
    )
    assert description == "HTTP 请求 → http://10.0.0.5:8080（来自环境变量 http_proxy）"
    assert describe_effective_proxy(None, True, environ={"HTTPS_PROXY": "http://10.0.0.6:8080", "https_proxy": ""}) is (
        None
    )


def test_describe_effective_proxy_normalizes_schemeless_values():
    # httpx 会为无 scheme 的代理值补全 http://
    description = describe_effective_proxy(None, True, environ={"ALL_PROXY": "127.0.0.1:7890"})
    assert description == "http://127.0.0.1:7890（来自环境变量 ALL_PROXY）"


def test_sanitize_proxy_url():
    assert sanitize_proxy_url("http://user:secret@10.0.0.1:8080") == "http://10.0.0.1:8080"
    assert sanitize_proxy_url("socks5://user@127.0.0.1:1080") == "socks5://127.0.0.1:1080"
    assert sanitize_proxy_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert sanitize_proxy_url("127.0.0.1:7890") == "127.0.0.1:7890"


@as_sync
async def test_max_retry_failure_carries_last_error_type():
    @MaxRetry(max_retry=0)
    async def always_connect_error() -> None:
        raise httpx.ConnectError("")

    result = await always_connect_error()
    match result:
        case Failure(error):
            assert "ConnectError" in str(error)
        case _:
            pytest.fail(f"expected Failure, got {result}")
