import aiohttp
import pytest

from yutto.api.space import get_uploader_name, get_uploader_space_all_videos_avids
from yutto.typing import AId, BvId, MId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functiontools.sync import sync


@pytest.mark.api
@sync
async def test_get_uploader_space_all_videos_avids():
    mid = MId("100969474")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        all_avid = await get_uploader_space_all_videos_avids(session, mid=mid)
        assert len(all_avid) > 0
        assert AId("371660125") in all_avid or BvId("BV1vZ4y1M7mQ") in all_avid


@pytest.mark.api
@sync
async def test_get_uploader_name():
    mid = MId("100969474")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        username = await get_uploader_name(session, mid=mid)
        assert username == "时雨千陌"
