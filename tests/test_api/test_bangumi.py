from __future__ import annotations

from typing import Any, cast

import pytest
from returns.result import Success

from yutto.api.bangumi import (
    get_bangumi_list,
    get_bangumi_playurl,
    get_bangumi_subtitles,  # noqa: F401
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.core.execution import ExecutionScope
from yutto.types import BvId, CId, EpisodeId, MediaId, SeasonId
from yutto.utils.fetcher import Fetcher, create_client
from yutto.utils.functional import as_sync


@pytest.mark.api
@as_sync
async def test_get_bangumi_list_reuses_season_metadata(monkeypatch: pytest.MonkeyPatch):
    requested_urls: list[str] = []

    async def fake_fetch_json(scope: ExecutionScope, url: str):
        requested_urls.append(url)
        return Success(
            {
                "result": {
                    "title": "葬送的芙莉莲",
                    "evaluate": "寿命逾千年的魔法使芙莉莲，踏上了了解人类的旅途。",
                    "styles": ["漫画改", "奇幻"],
                    "up_info": {
                        "mid": 928123,
                        "uname": "哔哩哔哩番剧",
                        "avatar": "https://i1.hdslb.com/avatar.jpg",
                    },
                    "section": [],
                    "episodes": [
                        {
                            "title": "1",
                            "long_title": "冒险的结束",
                            "cid": 1277806556,
                            "id": 779775,
                            "bvid": "BV1Nw411C7qS",
                            "duration": 1559933,
                            "badge": "",
                            "share_copy": "《葬送的芙莉莲》第1话 冒险的结束",
                            "cover": "https://i0.hdslb.com/cover.png",
                            "pub_time": 1698148800,
                        }
                    ],
                }
            }
        )

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)

    result = await get_bangumi_list(ExecutionScope(cast("Any", object())), SeasonId("43145"))
    item = result["pages"][0]

    assert requested_urls == ["http://api.bilibili.com/pgc/view/web/season?season_id=43145"]
    assert item["name"] == "第1话 冒险的结束"
    assert item["duration"] == 1559933
    assert item["metadata"]["show_title"] == "《葬送的芙莉莲》第1话 冒险的结束"
    assert item["metadata"]["plot"] == "寿命逾千年的魔法使芙莉莲，踏上了了解人类的旅途。"
    assert item["metadata"]["tag"] == ["漫画改", "奇幻"]
    assert item["metadata"]["premiered"] == 1698148800
    assert item["metadata"]["thumb"] == "https://i0.hdslb.com/cover.png"
    assert item["metadata"]["actor"] == [
        {
            "name": "哔哩哔哩番剧",
            "role": "UP主",
            "thumb": "https://i1.hdslb.com/avatar.jpg",
            "profile": "https://space.bilibili.com/928123",
            "order": 0,
        }
    ]


@pytest.mark.api
@as_sync
async def test_get_bangumi_list_falls_back_when_optional_metadata_is_empty(monkeypatch: pytest.MonkeyPatch):
    async def fake_fetch_json(scope: ExecutionScope, url: str):
        return Success(
            {
                "result": {
                    "title": "番剧",
                    "evaluate": "",
                    "styles": [],
                    "section": [],
                    "episodes": [
                        {
                            "title": "1",
                            "long_title": "",
                            "cid": 10,
                            "id": 20,
                            "bvid": "BV1f34y1k7D5",
                            "duration": 0,
                            "badge": "",
                            "share_copy": "番剧第1话",
                            "cover": "",
                            "pub_time": 1700000000,
                        }
                    ],
                }
            }
        )

    monkeypatch.setattr(Fetcher, "fetch_json", fake_fetch_json)

    item = (await get_bangumi_list(ExecutionScope(cast("Any", object())), SeasonId("1")))["pages"][0]

    assert item["duration"] == 0
    assert item["metadata"]["plot"] == "番剧第1话"
    assert item["metadata"]["tag"] == []
    assert item["metadata"]["actor"] == []


@pytest.mark.api
@as_sync
async def test_get_season_id_by_media_id():
    media_id = MediaId("28223066")
    season_id_excepted = SeasonId("28770")
    async with create_client() as client:
        scope = ExecutionScope(client)
        season_id = await get_season_id_by_media_id(scope, media_id)
        assert season_id == season_id_excepted


@pytest.mark.api
@as_sync
@pytest.mark.parametrize("episode_id", [EpisodeId("314477"), EpisodeId("300998")])
async def test_get_season_id_by_episode_id(episode_id: EpisodeId):
    season_id_excepted = SeasonId("28770")
    async with create_client() as client:
        scope = ExecutionScope(client)
        season_id = await get_season_id_by_episode_id(scope, episode_id)
        assert season_id == season_id_excepted


@pytest.mark.api
@as_sync
async def test_get_bangumi_title():
    season_id = SeasonId("28770")
    async with create_client() as client:
        scope = ExecutionScope(client)
        title = (await get_bangumi_list(scope, season_id))["title"]
        assert title == "我的三体之章北海传"


@pytest.mark.api
@as_sync
async def test_get_bangumi_list():
    season_id = SeasonId("28770")
    async with create_client() as client:
        scope = ExecutionScope(client)
        bangumi_list = (await get_bangumi_list(scope, season_id))["pages"]
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
    cid = CId("144541892")
    async with create_client() as client:
        scope = ExecutionScope(client)
        playlist = await get_bangumi_playurl(scope, avid, cid)
        assert len(playlist[0]) > 0
        assert len(playlist[1]) > 0


@pytest.mark.api
@as_sync
async def test_get_bangumi_subtitles():
    # TODO: 暂未找到需要字幕的番剧（非港澳台）
    pass
