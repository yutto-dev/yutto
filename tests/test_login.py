from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

import yutto.login as login_module
from yutto._native import HttpTransportError
from yutto.api.user_info import USER_INFO_API
from yutto.auth import load_auth, save_auth
from yutto.exceptions import ErrorCode
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from pathlib import Path


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


def test_run_login_saves_and_validates_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    clients: list[dict[str, Any]] = []
    requested: list[str] = []
    redirect = "https://passport.bilibili.com/confirmed?SESSDATA=sess%2Cdata&bili_jct=csrf-token"

    class LoginSession:
        async def get(self, url: str, **kwargs: Any):
            requested.append(url)
            if url == login_module.QR_GENERATE_API:
                payload = {"code": 0, "data": {"url": "https://example.com/qr", "qrcode_key": "qr-key"}}
            elif url == login_module.QR_POLL_API:
                assert dict(kwargs["params"])["qrcode_key"] == "qr-key"
                payload = {"code": 0, "data": {"code": 0, "url": redirect}}
            elif url == USER_INFO_API:
                payload = {"data": {"vipStatus": 0, "isLogin": True}}
            else:
                assert url == redirect
                payload = {}
            return SimpleNamespace(body=json.dumps(payload).encode(), url=url, raise_for_status=lambda: None)

        def cookie(self, name: str, *, url: str) -> None:
            return None

    @asynccontextmanager
    async def create_client(**kwargs: Any):
        clients.append(kwargs)
        yield LoginSession()

    monkeypatch.setattr(login_module, "create_client", create_client)
    auth_file = tmp_path / "auth.toml"
    login_module.run_auth(
        SimpleNamespace(
            auth_command="login",
            proxy="auto",
            auth_file=auth_file,
            auth_profile="test",
            mode="terminal",
            timeout=10,
            poll_interval=0,
        )
    )

    assert load_auth(auth_file, "test") == {"SESSDATA": "sess,data", "bili_jct": "csrf-token"}
    assert requested == [login_module.QR_GENERATE_API, login_module.QR_POLL_API, redirect, USER_INFO_API]
    assert len(clients) == 2
    assert all(client["verify"] is True for client in clients)
    assert clients[1]["cookies"] == {"SESSDATA": "sess%2Cdata", "bili_jct": "csrf-token"}
    output = capsys.readouterr().out
    assert "登录成功，已写入认证文件" in output
    assert "sess%2Cdata" not in output and "csrf-token" not in output


@as_sync
async def test_poll_qr_login_reports_status_changes_and_returns_redirect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    responses = iter(
        [
            {"code": 0, "data": {"code": login_module.QR_STATUS_NOT_SCANNED}},
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

    async def poll_request(session: object, url: str, *, params: dict[str, str]) -> dict[str, Any]:
        assert session is fake_session
        assert url == login_module.QR_POLL_API
        captured_params.append(dict(params))
        return next(responses)

    fake_session = object()
    captured_params: list[dict[str, str]] = []
    monkeypatch.setattr(login_module, "request_json", poll_request)

    assert (
        await login_module.poll_qr_login(cast("Any", fake_session), "qr-key", timeout=10, poll_interval=0)
        == "https://passport.bilibili.com/confirmed"
    )
    assert captured_params == [{"qrcode_key": "qr-key", "source": "main-fe-header"}] * 4
    output = capsys.readouterr().out
    assert output.count("二维码待扫描") == 1
    assert output.count("已扫码，请在 App 内确认登录") == 1


@as_sync
async def test_poll_qr_login_rejects_invalid_intervals():
    for poll_interval in (-1, float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError, match="poll_interval must be finite and non-negative"):
            await login_module.poll_qr_login(
                cast("Any", object()),
                "qr-key",
                timeout=10,
                poll_interval=poll_interval,
            )


@as_sync
async def test_complete_login_falls_back_to_redirect_query(capsys: pytest.CaptureFixture[str]):
    redirect_url = "https://passport.bilibili.com/confirmed?SESSDATA=sess%2Cdata&bili_jct=csrf-token"

    class FailedRedirectSession:
        async def get(self, url: str) -> None:
            raise HttpTransportError("redirect failed")

        def cookie(self, name: str, *, url: str) -> None:
            return None

    assert await login_module.complete_login(cast("Any", FailedRedirectSession()), redirect_url) == (
        redirect_url,
        "sess,data",
        "csrf-token",
    )
    assert "将尝试从返回 URL 提取 cookies" in capsys.readouterr().out


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


@pytest.mark.parametrize(
    ("state", "exit_code", "message"),
    [
        ("vip", None, "大会员"),
        ("logged-in", None, "当前账号已登录，但不是大会员"),
        ("missing", ErrorCode.NOT_LOGIN_ERROR.value, "未找到可用认证信息"),
        ("invalid-file", ErrorCode.WRONG_ARGUMENT_ERROR.value, "认证信息文件格式无效"),
        ("expired", ErrorCode.NOT_LOGIN_ERROR.value, "已失效或尚未登录"),
        ("network-error", ErrorCode.HTTP_STATUS_ERROR.value, "登录状态检查失败"),
    ],
)
def test_auth_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    state: str,
    exit_code: int | None,
    message: str,
):
    auth_file = tmp_path / "auth.toml"
    if state == "invalid-file":
        auth_file.write_text("[invalid")
    elif state != "missing":
        save_auth(auth_file, "test", "sessdata", None)

    async def fetch_user_info(auth, *, proxy: str | None, trust_env: bool):
        assert state not in {"missing", "invalid-file"}
        assert auth == {"SESSDATA": "sessdata", "bili_jct": None}
        assert proxy == "https://127.0.0.1:7890" and trust_env is False
        if state == "network-error":
            raise HttpTransportError("connection failed")
        return {"vip_status": state == "vip", "is_login": state != "expired"}

    monkeypatch.setattr(login_module, "fetch_authenticated_user_info", fetch_user_info)
    args = SimpleNamespace(
        auth_command="status", proxy="https://127.0.0.1:7890", auth="", auth_file=auth_file, auth_profile="test"
    )
    if exit_code is None:
        login_module.run_auth(args)
    else:
        with pytest.raises(SystemExit) as exc_info:
            login_module.run_auth(args)
        assert exc_info.value.code == exit_code
    assert message in capsys.readouterr().out


def test_auth_logout_removes_only_selected_profile_and_is_idempotent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    auth_file = tmp_path / "auth.toml"
    save_auth(auth_file, "test", "sessdata", None)
    save_auth(auth_file, "other", "keep", None)
    args = SimpleNamespace(auth_command="logout", auth_file=auth_file, auth_profile="test")
    login_module.run_auth(args)
    assert load_auth(auth_file, "test") is None
    assert load_auth(auth_file, "other") == {"SESSDATA": "keep", "bili_jct": None}
    assert "已退出登录并移除认证信息" in capsys.readouterr().out
    login_module.run_auth(args)
    assert "无需退出" in capsys.readouterr().out


@pytest.mark.parametrize("inline_auth", [False, True], ids=["invalid-file", "inline-auth"])
def test_auth_logout_rejects_invalid_auth(tmp_path: Path, capsys: pytest.CaptureFixture[str], inline_auth: bool):
    auth_file = tmp_path / "auth.toml"
    auth_file.write_text("[invalid")
    with pytest.raises(SystemExit) as exc_info:
        login_module.run_auth(
            SimpleNamespace(
                auth_command="logout",
                auth="SESSDATA=inline" if inline_auth else "",
                auth_file=auth_file,
                auth_profile="default",
            )
        )
    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert ("inline auth" if inline_auth else "认证信息文件格式无效") in capsys.readouterr().out
    assert auth_file.read_text() == "[invalid"
