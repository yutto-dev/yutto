from __future__ import annotations

import aiohttp
import pytest

from yutto.api.user_info import get_user_info
from yutto.utils.fetcher import Fetcher
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
async def test_get_user_info():
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        user_info = await get_user_info(session)
        assert not user_info["vip_status"]
        assert not user_info["is_login"]
