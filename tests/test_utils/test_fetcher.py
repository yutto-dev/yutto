from __future__ import annotations

import ssl
from typing import Any, Protocol, cast

import pytest
from returns.result import Failure, Success
from yutto_core import HttpStatusError, SessionClosedError

import yutto.utils.fetcher as fetcher_module
from yutto.core.execution import ExecutionScope
from yutto.utils.fetcher import Fetcher, create_client, create_sync_client, resolve_proxy
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


def test_resolve_proxy_rejects_invalid_scheme():
    with pytest.raises(ValueError, match="proxy 参数值"):
        resolve_proxy("ftp://127.0.0.1:21")


@as_sync
async def test_create_client_keeps_download_tls_verification_disabled_and_closes(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    class FakeNativeSession:
        is_closed = False

        def __init__(self, **kwargs: Any):
            captured.update(kwargs)

        def close(self) -> None:
            self.is_closed = True

    monkeypatch.setattr(fetcher_module, "NativeSession", FakeNativeSession)

    async with create_client() as session:
        assert not session.is_closed

    assert session.is_closed
    assert captured["accept_invalid_certs"] is True
    assert captured["use_system_proxy"] is True
    assert captured["read_timeout"] == 5
    assert captured["connect_timeout"] == 5


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


class _StatusResponse:
    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        self.body = b"failed"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise HttpStatusError(f"HTTP status {self.status_code}")


class _StatusSession:
    def __init__(self, status_code: int):
        self.status_code = status_code

    async def get(self, url: str, **kwargs: Any) -> _StatusResponse:
        return _StatusResponse(self.status_code, url)


@as_sync
async def test_fetcher_preserves_httpx_query_parameter_encoding():
    class QuerySession(_StatusSession):
        params: list[tuple[str, str]] | None = None

        async def get(self, url: str, **kwargs: Any) -> _StatusResponse:
            self.params = kwargs["params"]
            return await super().get(url, **kwargs)

    session = QuerySession(200)
    scope = ExecutionScope(cast("Any", session))

    assert await Fetcher.fetch_bin(
        scope,
        "https://example.com",
        params={
            "none": None,
            "true": True,
            "false": False,
            "list": [1, 2],
            "tuple": ("x", "y"),
            "scalar": 3,
        },
    ) == Success(b"failed")
    assert session.params == [
        ("none", ""),
        ("true", "true"),
        ("false", "false"),
        ("list", "1"),
        ("list", "2"),
        ("tuple", "x"),
        ("tuple", "y"),
        ("scalar", "3"),
    ]


@as_sync
async def test_fetch_bin_keeps_non_success_status_as_success_none():
    scope = ExecutionScope(cast("Any", _StatusSession(404)))
    match await Fetcher.fetch_bin(scope, "https://example.com"):
        case Success(None):
            pass
        case result:
            pytest.fail(f"expected Success(None), got {result}")


@as_sync
async def test_fetch_json_retries_non_success_status():
    scope = ExecutionScope(cast("Any", _StatusSession(404)))
    match await Fetcher.fetch_json(scope, "https://example.com"):
        case Failure(error):
            assert error.message == "超出最大重试次数！"
        case result:
            pytest.fail(f"expected Failure, got {result}")


@as_sync
async def test_get_redirected_url_keeps_non_success_status_as_url():
    scope = ExecutionScope(cast("Any", _StatusSession(404)))
    match await Fetcher.get_redirected_url(scope, "https://example.com"):
        case Success(url):
            assert url == "https://example.com"
        case result:
            pytest.fail(f"expected Success, got {result}")


@as_sync
async def test_touch_url_keeps_non_success_status_as_success_none():
    scope = ExecutionScope(cast("Any", _StatusSession(404)))
    match await Fetcher.touch_url(scope, "https://example.com"):
        case Success(None):
            pass
        case result:
            pytest.fail(f"expected Success(None), got {result}")


@pytest.mark.processor
@as_sync
async def test_touch_url_cache_is_scoped_to_execution_scope():
    class CountingSession(_StatusSession):
        def __init__(self):
            super().__init__(204)
            self.calls = 0

        async def get(self, url: str, **kwargs: Any) -> _StatusResponse:
            self.calls += 1
            return await super().get(url, **kwargs)

    first_session = CountingSession()
    second_session = CountingSession()
    first_scope = ExecutionScope(cast("Any", first_session))
    second_scope = ExecutionScope(cast("Any", second_session))

    assert isinstance(await Fetcher.touch_url(first_scope, "https://example.com"), Success)
    assert isinstance(await Fetcher.touch_url(first_scope, "https://example.com"), Success)
    assert isinstance(await Fetcher.touch_url(second_scope, "https://example.com"), Success)
    assert first_session.calls == 1
    assert second_session.calls == 1


@as_sync
async def test_fetcher_does_not_retry_a_closed_session():
    class ClosedSession:
        async def get(self, url: str, **kwargs: Any) -> None:
            raise SessionClosedError("closed")

    scope = ExecutionScope(cast("Any", ClosedSession()))
    with pytest.raises(SessionClosedError, match="closed"):
        await Fetcher.touch_url(scope, "https://example.com")
