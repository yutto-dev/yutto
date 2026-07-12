from __future__ import annotations

from typing import Any, cast

import pytest
from returns.result import Success

from yutto.api.user_info import get_user_info, parse_user_info, user_info_matches
from yutto.utils.fetcher import Fetcher, FetcherContext, create_client
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
    ctx = FetcherContext()
    async with create_client() as client:
        user_info = await get_user_info(ctx, client)
        assert not user_info["vip_status"]
        assert not user_info["is_login"]


@pytest.mark.processor
@as_sync
async def test_user_info_cache_is_scoped_to_fetcher_context(monkeypatch: pytest.MonkeyPatch):
    responses = iter(
        [
            {"data": {"vipStatus": 1, "isLogin": True}},
            {"data": {"vipStatus": 0, "isLogin": False}},
        ]
    )
    calls = 0

    async def fake_fetch_json(ctx, client, url):
        nonlocal calls
        calls += 1
        return Success(next(responses))

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)
    first_context = FetcherContext()
    second_context = FetcherContext()
    client = cast("Any", object())

    assert await get_user_info(first_context, client) == {"vip_status": True, "is_login": True}
    assert await get_user_info(first_context, client) == {"vip_status": True, "is_login": True}
    assert await get_user_info(second_context, client) == {"vip_status": False, "is_login": False}
    assert calls == 2
