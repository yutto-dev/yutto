import aiohttp
import pytest

from yutto.api.ugc_video import get_ugc_video_list, get_ugc_video_playurl, get_ugc_video_subtitles
from yutto._typing import BvId, CId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


@pytest.mark.api
@as_sync
async def test_get_ugc_video_title():
    avid = BvId("BV1vZ4y1M7mQ")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        title = (await get_ugc_video_list(session, avid))["title"]
        assert title == "用 bilili 下载 B 站视频"


@pytest.mark.api
@as_sync
async def test_get_ugc_video_list():
    avid = BvId("BV1vZ4y1M7mQ")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        ugc_video_list = (await get_ugc_video_list(session, avid))["pages"]
        assert ugc_video_list[0]["id"] == 1
        assert ugc_video_list[0]["name"] == "bilili 特性以及使用方法简单介绍"
        assert ugc_video_list[0]["cid"] == CId("222190584")
        assert ugc_video_list[0]["metadata"] is not None
        assert ugc_video_list[0]["metadata"]["title"] == "bilili 特性以及使用方法简单介绍"

        assert ugc_video_list[1]["id"] == 2
        assert ugc_video_list[1]["name"] == "bilili 环境配置方法"
        assert ugc_video_list[1]["cid"] == CId("222200470")
        assert ugc_video_list[1]["metadata"] is not None
        assert ugc_video_list[1]["metadata"]["title"] == "bilili 环境配置方法"


@pytest.mark.api
@as_sync
async def test_get_ugc_video_playurl():
    avid = BvId("BV1vZ4y1M7mQ")
    cid = CId("222190584")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        playlist = await get_ugc_video_playurl(session, avid, cid)
        assert len(playlist[0]) > 0
        assert len(playlist[1]) > 0


@pytest.mark.api
@as_sync
async def test_get_ugc_video_subtitles():
    avid = BvId("BV1Ra411A7kN")
    cid = CId("253246252")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        subtitles = await get_ugc_video_subtitles(session, avid=avid, cid=cid)
        assert len(subtitles) > 0
        assert len(subtitles[0]["lines"]) > 0
