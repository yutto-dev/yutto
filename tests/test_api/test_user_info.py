from __future__ import annotations

import pytest

from yutto.api.user_info import get_user_info
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
async def test_get_user_info():
    ctx = FetcherContext()
    async with create_client() as client:
        user_info = await get_user_info(ctx, client)
        assert not user_info["vip_status"]
        assert not user_info["is_login"]
