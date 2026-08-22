from __future__ import annotations

from types import MappingProxyType
from typing import Any, cast

import pytest
from returns.result import Failure, Success

import yutto.utils.fetcher as fetcher_module
from yutto._native import HttpStatusError, SessionClosedError
from yutto.core.execution import ExecutionScope
from yutto.utils.fetcher import Fetcher, cookies_from_auth, create_client, resolve_proxy
from yutto.utils.functional import as_sync


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

    class FakeYuttoSession:
        is_closed = False

        def __init__(self, **kwargs: Any):
            captured.update(kwargs)

        def close(self) -> None:
            self.is_closed = True

    monkeypatch.setattr(fetcher_module, "YuttoSession", FakeYuttoSession)

    async with create_client() as session:
        assert not session.is_closed

    assert session.is_closed
    assert captured["accept_invalid_certs"] is True
    assert captured["use_system_proxy"] is True
    assert captured["read_timeout"] == 5
    assert captured["connect_timeout"] == 5


@as_sync
async def test_create_client_accepts_read_only_mappings_and_none(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []

    class FakeYuttoSession:
        def __init__(self, **kwargs: Any):
            calls.append(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr(fetcher_module, "YuttoSession", FakeYuttoSession)

    async with create_client(
        headers=MappingProxyType({"X-Test": "value"}),
        cookies=MappingProxyType({"token": "secret"}),
    ):
        pass
    async with create_client(headers=None, cookies=None):
        pass

    assert calls[0]["headers"] == {"X-Test": "value"}
    assert calls[0]["cookies"] == {"token": "secret"}
    assert calls[1]["headers"] == {}
    assert calls[1]["cookies"] == {}


@as_sync
async def test_create_client_preserves_environment_ca_settings(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []

    class FakeYuttoSession:
        def __init__(self, **kwargs: Any):
            calls.append(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr(fetcher_module, "YuttoSession", FakeYuttoSession)
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/custom-ca.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "/tmp/custom-ca-directory")

    async with create_client(trust_env=True, verify=True):
        pass
    monkeypatch.delenv("SSL_CERT_FILE")
    async with create_client(trust_env=True, verify=True):
        pass
    async with create_client(trust_env=False, verify=True):
        pass

    assert calls[0]["ca_cert_file"] == "/tmp/custom-ca.pem"
    assert calls[0]["ca_cert_dir"] is None
    assert calls[1]["ca_cert_file"] is None
    assert calls[1]["ca_cert_dir"] == "/tmp/custom-ca-directory"
    assert calls[2]["ca_cert_file"] is None
    assert calls[2]["ca_cert_dir"] is None


def test_cookies_from_auth_returns_native_cookie_mapping():
    assert cookies_from_auth(None) == {}
    assert cookies_from_auth({"SESSDATA": "sess,data", "bili_jct": "csrf-token"}) == {
        "SESSDATA": "sess%2Cdata",
        "bili_jct": "csrf-token",
    }


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
async def test_get_size_reports_started_and_completed_with_probe_result(monkeypatch: pytest.MonkeyPatch):
    class SizeSession:
        def __init__(self):
            self.sizes = [42, None]
            self.urls: list[str] = []

        async def probe_size(self, url: str) -> int | None:
            self.urls.append(url)
            return self.sizes.pop(0)

    reports: list[str] = []
    monkeypatch.setattr(fetcher_module, "emit_download_report", lambda message, **_kwargs: reports.append(message))
    session = SizeSession()
    scope = ExecutionScope(cast("Any", session))

    assert await Fetcher.get_size(scope, "https://example.com/known") == Success(42)
    assert await Fetcher.get_size(scope, "https://example.com/unknown") == Success(None)
    assert session.urls == ["https://example.com/known", "https://example.com/unknown"]
    assert reports == [
        "Fetch size started: https://example.com/known",
        "Fetch size completed: https://example.com/known (42 bytes)",
        "Fetch size started: https://example.com/unknown",
        "Fetch size completed: https://example.com/unknown (size unknown)",
    ]


@as_sync
async def test_fetcher_preserves_query_parameter_encoding():
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
