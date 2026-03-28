from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx

import yutto.login as login_module
from yutto.api.user_info import USER_INFO_API

if TYPE_CHECKING:
    import pytest


def test_validate_saved_auth_uses_sync_client_with_auth_cookies(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}
    fake_client = object()

    @contextmanager
    def fake_create_sync_client(**kwargs: Any):
        calls.update(kwargs)
        yield fake_client

    def fake_request_json(client: object, url: str, *, params: dict[str, str]) -> dict[str, Any]:
        calls["client"] = client
        calls["url"] = url
        calls["params"] = params
        return {"data": {"vipStatus": 0, "isLogin": True}}

    monkeypatch.setattr(login_module, "create_sync_client", fake_create_sync_client)
    monkeypatch.setattr(login_module, "request_json", fake_request_json)

    assert login_module.validate_saved_auth(
        {"SESSDATA": "sess,data", "bili_jct": "csrf-token"},
        proxy="https://127.0.0.1:7890",
        trust_env=False,
    )

    cookies = calls["cookies"]
    assert isinstance(cookies, httpx.Cookies)
    assert cookies.get("SESSDATA") == "sess%2Cdata"
    assert cookies.get("bili_jct") == "csrf-token"
    assert calls["proxy"] == "https://127.0.0.1:7890"
    assert calls["trust_env"] is False
    assert calls["verify"] is True
    assert calls["client"] is fake_client
    assert calls["url"] == USER_INFO_API
    assert calls["params"] == {}


def test_run_login_uses_verified_sync_client(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}
    fake_client = object()

    @contextmanager
    def fake_create_sync_client(**kwargs: Any):
        calls.update(kwargs)
        yield fake_client

    def fake_generate_qr_login(client: object) -> tuple[str, str]:
        return ("https://example.com/qr", "qr-key")

    def fake_show_qr_code(url: str, mode: str) -> None:
        return None

    def fake_poll_qr_login(client: object, qrcode_key: str, *, timeout: int, poll_interval: float) -> str:
        return "https://example.com/redirect"

    def fake_complete_login(client: object, redirect_url: str) -> tuple[str, str | None, str | None]:
        return ("https://www.bilibili.com", "sessdata", "csrf-token")

    def fake_resolve_auth_file(args: SimpleNamespace) -> Path:
        return Path("/tmp/auth.toml")

    def fake_save_auth(auth_file: Path, profile: str, sessdata: str, bili_jct: str | None) -> None:
        return None

    def fake_validate_saved_auth(auth: dict[str, str | None], *, proxy: str | None, trust_env: bool) -> bool:
        return True

    monkeypatch.setattr(login_module, "create_sync_client", fake_create_sync_client)
    monkeypatch.setattr(login_module, "generate_qr_login", fake_generate_qr_login)
    monkeypatch.setattr(login_module, "show_qr_code", fake_show_qr_code)
    monkeypatch.setattr(login_module, "poll_qr_login", fake_poll_qr_login)
    monkeypatch.setattr(login_module, "complete_login", fake_complete_login)
    monkeypatch.setattr(login_module, "resolve_auth_file", fake_resolve_auth_file)
    monkeypatch.setattr(login_module, "save_auth", fake_save_auth)
    monkeypatch.setattr(login_module, "validate_saved_auth", fake_validate_saved_auth)

    login_module.run_login(
        SimpleNamespace(
            proxy="auto",
            auth_profile="default",
            mode="terminal",
            timeout=180,
            poll_interval=2.0,
        )
    )

    assert calls["verify"] is True
