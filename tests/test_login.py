from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from yutto_core import HttpTransportError

import yutto.login as login_module
from yutto.api.user_info import USER_INFO_API
from yutto.exceptions import ErrorCode
from yutto.utils.functional import as_sync


@as_sync
async def test_validate_saved_auth_uses_yutto_session_with_auth_cookies(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}
    fake_session = object()

    @asynccontextmanager
    async def fake_create_client(**kwargs: Any):
        calls.update(kwargs)
        yield fake_session

    async def fake_request_json(session: object, url: str, *, params: dict[str, str]) -> dict[str, Any]:
        calls["session"] = session
        calls["url"] = url
        calls["params"] = params
        return {"data": {"vipStatus": 0, "isLogin": True}}

    monkeypatch.setattr(login_module, "create_client", fake_create_client)
    monkeypatch.setattr(login_module, "request_json", fake_request_json)

    assert await login_module.validate_saved_auth(
        {"SESSDATA": "sess,data", "bili_jct": "csrf-token"},
        proxy="https://127.0.0.1:7890",
        trust_env=False,
    )

    assert calls["cookies"] == {"SESSDATA": "sess%2Cdata", "bili_jct": "csrf-token"}
    assert calls["proxy"] == "https://127.0.0.1:7890"
    assert calls["trust_env"] is False
    assert calls["timeout"] == 5
    assert calls["verify"] is True
    assert calls["session"] is fake_session
    assert calls["url"] == USER_INFO_API
    assert calls["params"] == {}


@as_sync
async def test_run_login_reuses_one_verified_yutto_session(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}
    sessions: list[object] = []
    fake_session = object()

    @asynccontextmanager
    async def fake_create_client(**kwargs: Any):
        calls.update(kwargs)
        yield fake_session

    async def fake_generate_qr_login(session: object) -> tuple[str, str]:
        sessions.append(session)
        return ("https://example.com/qr", "qr-key")

    def fake_show_qr_code(url: str, mode: str) -> None:
        calls["qr"] = (url, mode)

    async def fake_poll_qr_login(
        session: object,
        qrcode_key: str,
        *,
        timeout: int,
        poll_interval: float,
    ) -> str:
        sessions.append(session)
        calls["poll"] = (qrcode_key, timeout, poll_interval)
        return "https://example.com/redirect"

    async def fake_complete_login(
        session: object,
        redirect_url: str,
    ) -> tuple[str, str | None, str | None]:
        sessions.append(session)
        calls["redirect_url"] = redirect_url
        return ("https://www.bilibili.com", "sessdata", "csrf-token")

    def fake_resolve_auth_file(args: SimpleNamespace) -> Path:
        return Path("/tmp/auth.toml")

    def fake_save_auth(auth_file: Path, profile: str, sessdata: str, bili_jct: str | None) -> None:
        calls["saved"] = (auth_file, profile, sessdata, bili_jct)

    async def fake_validate_saved_auth(
        auth: dict[str, str | None],
        *,
        proxy: str | None,
        trust_env: bool,
    ) -> bool:
        calls["validated"] = (auth, proxy, trust_env)
        return True

    monkeypatch.setattr(login_module, "create_client", fake_create_client)
    monkeypatch.setattr(login_module, "generate_qr_login", fake_generate_qr_login)
    monkeypatch.setattr(login_module, "show_qr_code", fake_show_qr_code)
    monkeypatch.setattr(login_module, "poll_qr_login", fake_poll_qr_login)
    monkeypatch.setattr(login_module, "complete_login", fake_complete_login)
    monkeypatch.setattr(login_module, "resolve_auth_file", fake_resolve_auth_file)
    monkeypatch.setattr(login_module, "save_auth", fake_save_auth)
    monkeypatch.setattr(login_module, "validate_saved_auth", fake_validate_saved_auth)

    await login_module.run_login(
        SimpleNamespace(
            proxy="auto",
            auth_profile="default",
            mode="terminal",
            timeout=180,
            poll_interval=2.0,
        )
    )

    assert calls["verify"] is True
    assert calls["timeout"] == 10
    assert sessions == [fake_session, fake_session, fake_session]
    assert calls["qr"] == ("https://example.com/qr", "terminal")
    assert calls["poll"] == ("qr-key", 180, 2.0)
    assert calls["saved"] == (Path("/tmp/auth.toml"), "default", "sessdata", "csrf-token")


@as_sync
async def test_poll_qr_login_reports_status_changes_and_returns_redirect(monkeypatch: pytest.MonkeyPatch):
    responses = iter(
        [
            {"code": 0, "data": {"code": login_module.QR_STATUS_NOT_SCANNED}},
            {"code": 0, "data": {"code": login_module.QR_STATUS_SCANNED}},
            {
                "code": 0,
                "data": {
                    "code": login_module.QR_STATUS_CONFIRMED,
                    "url": "https://passport.bilibili.com/confirmed",
                },
            },
        ]
    )
    messages: list[str] = []
    sleeps: list[float] = []

    async def fake_sleep(interval: float) -> None:
        sleeps.append(interval)

    async def poll_request(session: object, url: str, *, params: dict[str, str]) -> dict[str, Any]:
        assert session is fake_session
        assert url == login_module.QR_POLL_API
        captured_params.append(dict(params))
        return next(responses)

    fake_session = object()
    captured_params: list[dict[str, str]] = []
    monkeypatch.setattr(login_module, "request_json", poll_request)
    monkeypatch.setattr(login_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(login_module.Logger, "info", messages.append)

    assert (
        await login_module.poll_qr_login(cast("Any", fake_session), "qr-key", timeout=10, poll_interval=0.25)
        == "https://passport.bilibili.com/confirmed"
    )
    assert captured_params == [
        {"qrcode_key": "qr-key", "source": "main-fe-header"},
        {"qrcode_key": "qr-key", "source": "main-fe-header"},
        {"qrcode_key": "qr-key", "source": "main-fe-header"},
    ]
    assert messages == ["二维码待扫描", "已扫码，请在 App 内确认登录"]
    assert sleeps == [0.25, 0.25]


@as_sync
async def test_poll_qr_login_rejects_negative_interval(monkeypatch: pytest.MonkeyPatch):
    fake_session = object()

    async def not_scanned(session: object, url: str, *, params: dict[str, str]) -> dict[str, Any]:
        assert session is fake_session
        assert url == login_module.QR_POLL_API
        assert params == {"qrcode_key": "qr-key", "source": "main-fe-header"}
        return {"code": 0, "data": {"code": login_module.QR_STATUS_NOT_SCANNED}}

    monkeypatch.setattr(login_module, "request_json", not_scanned)
    with pytest.raises(ValueError, match="poll_interval must be non-negative"):
        await login_module.poll_qr_login(cast("Any", fake_session), "qr-key", timeout=10, poll_interval=-1)


@as_sync
async def test_complete_login_falls_back_to_redirect_query(monkeypatch: pytest.MonkeyPatch):
    warnings: list[str] = []
    redirect_url = "https://passport.bilibili.com/confirmed?SESSDATA=sess%2Cdata&bili_jct=csrf-token"

    class FailedRedirectSession:
        async def get(self, url: str) -> None:
            raise HttpTransportError("redirect failed")

        def cookie(self, name: str, *, url: str) -> None:
            return None

    monkeypatch.setattr(login_module.Logger, "warning", warnings.append)

    assert await login_module.complete_login(cast("Any", FailedRedirectSession()), redirect_url) == (
        redirect_url,
        "sess,data",
        "csrf-token",
    )
    assert warnings and "将尝试从返回 URL 提取 cookies" in warnings[0]


def test_get_cookie_value_probes_bilibili_domains_in_priority_order():
    probes: list[str] = []

    class CookieSession:
        def cookie(self, name: str, *, url: str) -> str | None:
            assert name == "SESSDATA"
            probes.append(url)
            if url == "https://bilibili.com/":
                return "preferred"
            return None

    assert login_module.get_cookie_value(cast("Any", CookieSession()), "SESSDATA") == "preferred"
    assert probes == list(login_module.COOKIE_PROBE_URLS[:2])


def test_run_auth_is_the_single_sync_cli_boundary(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    async def fake_login(args: SimpleNamespace) -> None:
        calls.append(f"login:{args.auth_command}")

    async def fake_status(args: SimpleNamespace) -> None:
        calls.append(f"status:{args.auth_command}")

    def fake_logout(args: SimpleNamespace) -> None:
        calls.append(f"logout:{args.auth_command}")

    monkeypatch.setattr(login_module, "run_login", fake_login)
    monkeypatch.setattr(login_module, "run_auth_status", fake_status)
    monkeypatch.setattr(login_module, "run_auth_logout", fake_logout)

    for command in ("login", "status", "logout"):
        login_module.run_auth(SimpleNamespace(auth_command=command))

    assert calls == ["login:login", "status:status", "logout:logout"]


@as_sync
async def test_run_auth_status_reports_vip_login(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": "csrf-token"}

    async def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None],
        *,
        proxy: str | None,
        trust_env: bool,
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

    await login_module.run_auth_status(
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


@as_sync
async def test_run_auth_status_exits_when_auth_missing(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> None:
        return None

    def fake_warning(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module.Logger, "warning", fake_warning)

    with pytest.raises(SystemExit) as exc_info:
        await login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.NOT_LOGIN_ERROR.value
    assert "未找到可用认证信息" in calls["message"]


@as_sync
async def test_run_auth_status_exits_on_invalid_auth_file(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        raise ValueError("认证信息文件格式无效：/tmp/auth.toml")

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        await login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert "认证信息文件格式无效" in calls["message"]


@as_sync
async def test_run_auth_status_exits_when_not_logged_in(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": None}

    async def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None],
        *,
        proxy: str | None,
        trust_env: bool,
    ) -> dict[str, bool]:
        return {"vip_status": False, "is_login": False}

    def fake_warning(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fake_fetch_authenticated_user_info)
    monkeypatch.setattr(login_module.Logger, "warning", fake_warning)

    with pytest.raises(SystemExit) as exc_info:
        await login_module.run_auth_status(
            SimpleNamespace(
                proxy="auto",
                auth="",
                auth_file=Path("/tmp/auth.toml"),
                auth_profile="default",
            )
        )

    assert exc_info.value.code == ErrorCode.NOT_LOGIN_ERROR.value
    assert "已失效或尚未登录" in calls["message"]


@as_sync
async def test_run_auth_status_exits_when_status_check_fails(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, Any] = {}

    def fake_resolve_auth(args: SimpleNamespace) -> dict[str, str | None]:
        return {"SESSDATA": "sessdata", "bili_jct": None}

    async def fake_fetch_authenticated_user_info(
        auth: dict[str, str | None],
        *,
        proxy: str | None,
        trust_env: bool,
    ) -> dict[str, bool]:
        raise RuntimeError("boom")

    def fake_error(message: str, *args: Any, **kwargs: Any) -> str:
        return str(calls.setdefault("message", message))

    monkeypatch.setattr(login_module, "resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fake_fetch_authenticated_user_info)
    monkeypatch.setattr(login_module.Logger, "error", fake_error)

    with pytest.raises(SystemExit) as exc_info:
        await login_module.run_auth_status(
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
