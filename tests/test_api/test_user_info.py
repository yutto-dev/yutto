import aiohttp
import pytest

from yutto.api.user_info import is_vip
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


@pytest.mark.api
@as_sync
async def test_is_vip():
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        assert not await is_vip(session)
