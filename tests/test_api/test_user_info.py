from __future__ import annotations

from typing import Any, cast

import pytest
from returns.result import Success

from yutto.api.user_info import get_user_info, get_wbi_img, parse_user_info, user_info_matches, validate_user_info
from yutto.core.execution import ExecutionScope
from yutto.types import UserInfo
from yutto.utils.fetcher import Fetcher, create_client
from yutto.utils.functional import as_sync


def test_parse_user_info():
    assert parse_user_info({"data": {"vipStatus": 1, "isLogin": True}}) == {"vip_status": True, "is_login": True}


def test_user_info_matches():
    assert user_info_matches({"vip_status": True, "is_login": True}, {"vip_status": True, "is_login": False})
    assert not user_info_matches({"vip_status": False, "is_login": True}, {"vip_status": True, "is_login": False})
    assert not user_info_matches({"vip_status": True, "is_login": False}, {"vip_status": False, "is_login": True})


@pytest.mark.api
@as_sync
async def test_get_user_info():
    async with create_client() as client:
        scope = ExecutionScope(client)
        user_info = await get_user_info(scope)
        assert not user_info["vip_status"]
        assert not user_info["is_login"]


@pytest.mark.processor
@as_sync
async def test_user_info_cache_is_scoped_to_execution_scope(monkeypatch: pytest.MonkeyPatch):
    responses = iter(
        [
            {"data": {"vipStatus": 1, "isLogin": True}},
            {"data": {"vipStatus": 0, "isLogin": False}},
        ]
    )
    calls = 0

    async def fake_fetch_json(scope, url):
        nonlocal calls
        calls += 1
        return Success(next(responses))

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)
    first_scope = ExecutionScope(cast("Any", object()))
    second_scope = ExecutionScope(cast("Any", object()))

    assert await get_user_info(first_scope) == {"vip_status": True, "is_login": True}
    assert await get_user_info(first_scope) == {"vip_status": True, "is_login": True}
    assert await get_user_info(second_scope) == {"vip_status": False, "is_login": False}
    assert calls == 2


@pytest.mark.processor
@as_sync
async def test_validate_user_info_reuses_execution_scope_client_and_cache(monkeypatch: pytest.MonkeyPatch):
    client = cast("Any", object())
    scope = ExecutionScope(client)
    clients: list[Any] = []

    async def fake_fetch_json(active_scope, url):
        clients.append(active_scope.client)
        return Success({"data": {"vipStatus": 1, "isLogin": True}})

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)

    requirements = UserInfo(vip_status=True, is_login=True)
    assert await validate_user_info(scope, requirements)
    assert await validate_user_info(scope, requirements)
    assert clients == [client]


@pytest.mark.processor
@as_sync
async def test_wbi_cache_is_scoped_to_execution_scope(monkeypatch: pytest.MonkeyPatch):
    responses = iter(
        [
            {
                "data": {
                    "wbi_img": {
                        "img_url": "https://example.com/first-img.png",
                        "sub_url": "https://example.com/first-sub.png",
                    }
                }
            },
            {
                "data": {
                    "wbi_img": {
                        "img_url": "https://example.com/second-img.png",
                        "sub_url": "https://example.com/second-sub.png",
                    }
                }
            },
        ]
    )
    calls = 0

    async def fake_fetch_json(scope, url):
        nonlocal calls
        calls += 1
        return Success(next(responses))

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)
    first_scope = ExecutionScope(cast("Any", object()))
    second_scope = ExecutionScope(cast("Any", object()))

    assert await get_wbi_img(first_scope) == {
        "img_key": "first-img",
        "sub_key": "first-sub",
    }
    assert await get_wbi_img(first_scope) == {
        "img_key": "first-img",
        "sub_key": "first-sub",
    }
    assert await get_wbi_img(second_scope) == {
        "img_key": "second-img",
        "sub_key": "second-sub",
    }
    assert calls == 2
