from __future__ import annotations

from contextlib import contextmanager
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
    assert calls["client"] is fake_client
    assert calls["url"] == USER_INFO_API
    assert calls["params"] == {}
