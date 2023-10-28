from __future__ import annotations

import aiohttp
import pytest

from yutto._typing import BvId, CId, EpisodeId, MediaId, SeasonId
from yutto.api.bangumi import (
    get_bangumi_list,
    get_bangumi_playurl,
    get_bangumi_subtitles,  # type: ignore
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.utils.fetcher import Fetcher
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
async def test_get_season_id_by_media_id():
    media_id = MediaId("28223066")
    season_id_excepted = SeasonId("28770")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        season_id = await get_season_id_by_media_id(session, media_id)
        assert season_id == season_id_excepted


@pytest.mark.api
@as_sync
@pytest.mark.parametrize("episode_id", [EpisodeId("314477"), EpisodeId("300998")])
async def test_get_season_id_by_episode_id(episode_id: EpisodeId):
    season_id_excepted = SeasonId("28770")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        season_id = await get_season_id_by_episode_id(session, episode_id)
        assert season_id == season_id_excepted


@pytest.mark.api
@as_sync
async def test_get_bangumi_title():
    season_id = SeasonId("28770")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        title = (await get_bangumi_list(session, season_id))["title"]
        assert title == "我的三体之章北海传"


@pytest.mark.api
@as_sync
async def test_get_bangumi_list():
    season_id = SeasonId("28770")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        bangumi_list = (await get_bangumi_list(session, season_id))["pages"]
        assert bangumi_list[0]["id"] == 1
        assert bangumi_list[0]["name"] == "第1话"
        assert bangumi_list[0]["cid"] == CId("144541892")
        assert bangumi_list[0]["metadata"] is not None
        assert bangumi_list[0]["metadata"]["title"] == "第1话"

        assert bangumi_list[8]["id"] == 9
        assert bangumi_list[8]["name"] == "第9话"
        assert bangumi_list[8]["cid"] == CId("162395026")
        assert bangumi_list[8]["metadata"] is not None
        assert bangumi_list[8]["metadata"]["title"] == "第9话"


@pytest.mark.api
@pytest.mark.ci_skip
@as_sync
async def test_get_bangumi_playurl():
    avid = BvId("BV1q7411v7Vd")
    episode_id = EpisodeId("300998")
    cid = CId("144541892")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        playlist = await get_bangumi_playurl(session, avid, episode_id, cid)
        assert len(playlist[0]) > 0
        assert len(playlist[1]) > 0


@pytest.mark.api
@as_sync
async def test_get_bangumi_subtitles():
    # TODO: 暂未找到需要字幕的番剧（非港澳台）
    pass
