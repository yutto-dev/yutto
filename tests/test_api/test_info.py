import aiohttp
import pytest

from yutto.api.info import get_video_info, is_vip
from yutto.typing import AId, BvId, CId, EpisodeId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import sync


@pytest.mark.api
@pytest.mark.ci_skip
@sync
async def test_get_video_info():
    bvid = BvId("BV1q7411v7Vd")
    aid = AId("84271171")
    avid = bvid
    episode_id = EpisodeId("300998")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        video_info = await get_video_info(session, avid=avid)
        assert video_info["avid"] == aid or video_info["avid"] == bvid
        assert video_info["aid"] == aid
        assert video_info["bvid"] == bvid
        assert video_info["episode_id"] == episode_id
        assert video_info["is_bangumi"] == True
        assert video_info["cid"] == CId("144541892")
        assert video_info["title"] == "【独播】我的三体之章北海传 第1集"


@pytest.mark.api
@sync
async def test_is_vip():
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        assert not await is_vip(session)
