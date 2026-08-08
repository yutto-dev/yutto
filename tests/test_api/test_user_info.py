from __future__ import annotations

import asyncio
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
async def test_validate_user_info_reuses_execution_scope_session_and_cache(monkeypatch: pytest.MonkeyPatch):
    session = cast("Any", object())
    scope = ExecutionScope(session)
    sessions: list[Any] = []

    async def fake_fetch_json(active_scope, url):
        sessions.append(active_scope.session)
        return Success({"data": {"vipStatus": 1, "isLogin": True}})

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)

    requirements = UserInfo(vip_status=True, is_login=True)
    assert await validate_user_info(scope, requirements)
    assert await validate_user_info(scope, requirements)
    assert sessions == [session]


@pytest.mark.processor
@as_sync
async def test_concurrent_user_info_reads_share_one_fetch(monkeypatch: pytest.MonkeyPatch):
    calls = 0

    async def fake_fetch_json(scope, url):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return Success({"data": {"vipStatus": 1, "isLogin": True}})

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)
    scope = ExecutionScope(cast("Any", object()))

    results = await asyncio.gather(get_user_info(scope), get_user_info(scope))

    assert results == [
        {"vip_status": True, "is_login": True},
        {"vip_status": True, "is_login": True},
    ]
    assert calls == 1


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


@pytest.mark.processor
@as_sync
async def test_concurrent_wbi_reads_share_one_fetch(monkeypatch: pytest.MonkeyPatch):
    calls = 0

    async def fake_fetch_json(scope, url):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return Success(
            {
                "data": {
                    "wbi_img": {
                        "img_url": "https://example.com/img.png",
                        "sub_url": "https://example.com/sub.png",
                    }
                }
            }
        )

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)
    scope = ExecutionScope(cast("Any", object()))

    results = await asyncio.gather(get_wbi_img(scope), get_wbi_img(scope))

    assert results == [
        {"img_key": "img", "sub_key": "sub"},
        {"img_key": "img", "sub_key": "sub"},
    ]
    assert calls == 1
