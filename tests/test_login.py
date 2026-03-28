from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import yutto.login as login_module
from yutto.api.user_info import USER_INFO_API
from yutto.exceptions import ErrorCode


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


def test_run_auth_status_reports_vip_login(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": "csrf-token"}

    def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None], *, proxy: str | None, trust_env: bool
    ) -> dict[str, bool]:
        calls["proxy"] = proxy
        calls["trust_env"] = trust_env
        return {"vip_status": True, "is_login": True}

    def fake_custom(message: str, badge: object, *args: Any, **kwargs: Any) -> None:
        calls["message"] = message
        calls["badge"] = str(badge)

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fake_fetch_authenticated_user_info)
    monkeypatch.setattr(login_module.Logger, "custom", fake_custom)

    login_module.run_auth_status(
        SimpleNamespace(
            proxy="https://127.0.0.1:7890",
            auth="",
            auth_file=Path("/tmp/auth.toml"),
            auth_profile="default",
        )
    )

    assert calls["proxy"] == "https://127.0.0.1:7890"
    assert calls["trust_env"] is False
    assert "当前认证信息有效" in calls["message"]
    assert "大会员" in calls["badge"]


def test_run_auth_status_exits_when_auth_missing(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> None:
        return None

    def fake_warning(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(
        login_module.Logger,
        "warning",
        fake_warning,
    )

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.NOT_LOGIN_ERROR.value
    assert "未找到可用认证信息" in calls["message"]


def test_run_auth_status_exits_on_invalid_auth_file(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        raise ValueError("认证信息文件格式无效：/tmp/auth.toml")

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert "认证信息文件格式无效" in calls["message"]


def test_run_auth_status_exits_when_not_logged_in(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": None}

    def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None], *, proxy: str | None, trust_env: bool
    ) -> dict[str, bool]:
        return {"vip_status": False, "is_login": False}

    def fake_warning(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fake_fetch_authenticated_user_info)
    monkeypatch.setattr(
        login_module.Logger,
        "warning",
        fake_warning,
    )

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.NOT_LOGIN_ERROR.value
    assert "已失效或尚未登录" in calls["message"]


def test_run_auth_status_exits_when_status_check_fails(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": None}

    def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None], *, proxy: str | None, trust_env: bool
    ) -> dict[str, bool]:
        raise RuntimeError("boom")

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fake_fetch_authenticated_user_info)
    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.HTTP_STATUS_ERROR.value
    assert "登录状态检查失败" in calls["message"]


def test_run_auth_logout_removes_auth(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_remove_auth(auth_file: Path, profile: str) -> bool:
        calls["auth_file"] = auth_file
        calls["profile"] = profile
        return True

    def fake_info(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "remove_auth", fake_remove_auth)
    monkeypatch.setattr(login_module.Logger, "info", fake_info)

    login_module.run_auth_logout(SimpleNamespace(auth_file=Path("/tmp/auth.toml"), auth_profile="default"))

    assert calls["auth_file"] == Path("/tmp/auth.toml")
    assert calls["profile"] == "default"
    assert "已退出登录并移除认证信息" in calls["message"]


def test_run_auth_logout_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_remove_auth(auth_file: Path, profile: str) -> bool:
        return False

    def fake_info(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "remove_auth", fake_remove_auth)
    monkeypatch.setattr(login_module.Logger, "info", fake_info)

    login_module.run_auth_logout(SimpleNamespace(auth_file=Path("/tmp/auth.toml"), auth_profile="default"))

    assert "无需退出" in calls["message"]


def test_run_auth_logout_exits_on_invalid_auth_file(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_remove_auth(auth_file: Path, profile: str) -> bool:
        raise ValueError("bad auth file")

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "remove_auth", fake_remove_auth)
    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_logout(SimpleNamespace(auth_file=Path("/tmp/auth.toml"), auth_profile="default"))

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert "bad auth file" in calls["message"]


def test_run_auth_logout_rejects_inline_auth(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth_logout(
            SimpleNamespace(
                auth="SESSDATA=inline-auth",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert "inline auth" in calls["message"]
