from __future__ import annotations

import pytest

from yutto._typing import AId, AudioUrlMeta, CId, EpisodeId, SeasonId, VideoUrlMeta
from yutto.api.cheese import (
    get_cheese_list,
    get_cheese_playurl,
    get_season_id_by_episode_id,
)
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
@pytest.mark.parametrize("episode_id", [EpisodeId("6945"), EpisodeId("6902")])
async def test_get_season_id_by_episode_id(episode_id: EpisodeId):
    season_id_excepted = SeasonId("298")
    ctx = FetcherContext()
    async with create_client() as client:
        season_id = await get_season_id_by_episode_id(ctx, client, episode_id)
        assert season_id == season_id_excepted


@pytest.mark.api
@as_sync
async def test_get_cheese_title():
    season_id = SeasonId("298")
    ctx = FetcherContext()
    async with create_client() as client:
        cheese_list = await get_cheese_list(ctx, client, season_id)
        title = cheese_list["title"]
        assert title == "林超：给年轻人的跨学科通识课"


@pytest.mark.api
@as_sync
async def test_get_cheese_list():
    season_id = SeasonId("298")
    ctx = FetcherContext()
    async with create_client() as client:
        cheese_list = (await get_cheese_list(ctx, client, season_id))["pages"]
        assert cheese_list[0]["id"] == 1
        assert cheese_list[0]["name"] == "【先导片】给年轻人的跨学科通识课"
        assert cheese_list[0]["cid"] == CId("344779477")

        assert cheese_list[25]["id"] == 26
        assert cheese_list[25]["name"] == "回到真实世界（下）"
        assert cheese_list[25]["cid"] == CId("506369050")


@pytest.mark.api
@pytest.mark.ci_skip
@as_sync
async def test_get_cheese_playurl():
    avid = AId("545852212")
    episode_id = EpisodeId("6902")
    cid = CId("344779477")
    ctx = FetcherContext()
    async with create_client() as client:
        playlist: tuple[list[VideoUrlMeta], list[AudioUrlMeta]] = await get_cheese_playurl(
            ctx, client, avid, episode_id, cid
        )
        assert len(playlist[0]) > 0
        assert len(playlist[1]) > 0


@pytest.mark.api
@as_sync
async def test_get_cheese_subtitles():
    # TODO: 暂未找到需要字幕的课程
    pass
