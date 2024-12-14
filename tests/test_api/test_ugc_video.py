from __future__ import annotations

import pytest

from yutto._typing import AId, BvId, CId, EpisodeId
from yutto.api.ugc_video import (
    get_ugc_video_info,
    get_ugc_video_list,
    get_ugc_video_playurl,
    get_ugc_video_subtitles,
)
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@pytest.mark.ci_skip
@as_sync
async def test_get_ugc_video_info():
    bvid = BvId("BV1q7411v7Vd")
    aid = AId("84271171")
    avid = bvid
    episode_id = EpisodeId("300998")
    ctx = FetcherContext()
    async with create_client() as client:
        video_info = await get_ugc_video_info(ctx, client, avid=avid)
        assert video_info["avid"] == aid or video_info["avid"] == bvid
        assert video_info["aid"] == aid
        assert video_info["bvid"] == bvid
        assert video_info["episode_id"] == episode_id
        assert video_info["is_bangumi"] is True
        assert video_info["cid"] == CId("144541892")
        assert video_info["title"] == "【独播】我的三体之章北海传 第1集"


@pytest.mark.api
@as_sync
async def test_get_ugc_video_title():
    avid = BvId("BV1vZ4y1M7mQ")
    ctx = FetcherContext()
    async with create_client() as client:
        title = (await get_ugc_video_list(ctx, client, avid))["title"]
        assert title == "用 bilili 下载 B 站视频"


@pytest.mark.api
@as_sync
async def test_get_ugc_video_list():
    avid = BvId("BV1vZ4y1M7mQ")
    ctx = FetcherContext()
    async with create_client() as client:
        ugc_video_list = (await get_ugc_video_list(ctx, client, avid))["pages"]
        assert ugc_video_list[0]["id"] == 1
        assert ugc_video_list[0]["name"] == "bilili 特性以及使用方法简单介绍"
        assert ugc_video_list[0]["cid"] == CId("222190584")
        assert ugc_video_list[0]["metadata"] is not None
        assert ugc_video_list[0]["metadata"]["title"] == "bilili 特性以及使用方法简单介绍"
        assert ugc_video_list[0]["metadata"]["website"] == "https://www.bilibili.com/video/BV1vZ4y1M7mQ"

        assert ugc_video_list[1]["id"] == 2
        assert ugc_video_list[1]["name"] == "bilili 环境配置方法"
        assert ugc_video_list[1]["cid"] == CId("222200470")
        assert ugc_video_list[1]["metadata"] is not None
        assert ugc_video_list[1]["metadata"]["title"] == "bilili 环境配置方法"
        assert ugc_video_list[0]["metadata"]["website"] == "https://www.bilibili.com/video/BV1vZ4y1M7mQ"


@pytest.mark.api
@pytest.mark.ci_skip
@as_sync
async def test_get_ugc_video_playurl():
    avid = BvId("BV1vZ4y1M7mQ")
    cid = CId("222190584")
    ctx = FetcherContext()
    async with create_client() as client:
        playlist = await get_ugc_video_playurl(ctx, client, avid, cid)
        assert len(playlist[0]) > 0
        assert len(playlist[1]) > 0


# The latest subtitle API needs login, so this test is skipped.
# We need to find a way to test theses APIs.
@pytest.mark.skip
@pytest.mark.api
@as_sync
async def test_get_ugc_video_subtitles():
    avid = BvId("BV1Ra411A7kN")
    cid = CId("253246252")
    ctx = FetcherContext()
    async with create_client() as client:
        subtitles = await get_ugc_video_subtitles(ctx, client, avid=avid, cid=cid)
        assert len(subtitles) > 0
        assert len(subtitles[0]["lines"]) > 0
