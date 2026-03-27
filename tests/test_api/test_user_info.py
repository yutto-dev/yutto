from __future__ import annotations

import pytest

from yutto.api.user_info import get_user_info, parse_user_info, user_info_matches
from yutto.utils.fetcher import FetcherContext, create_client
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
