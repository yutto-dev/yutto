from __future__ import annotations

from typing import Any, cast

import pytest
from returns.result import Success

from yutto.api.space import (
    SPACE_ARC_WEB_LOCATION,
    _build_user_space_params,
    get_all_favourites,
    get_favourite_avids,
    get_favourite_info,
    get_medialist_avids,
    get_medialist_title,
    get_user_name,
    get_user_space_all_videos_avids,
)
from yutto.api.user_info import DM_IMG_INTER, X_BILI_DEVICE_REQ_JSON, WbiImg
from yutto.core.execution import ExecutionScope
from yutto.types import AId, BvId, FId, MId, SeriesId
from yutto.utils.fetcher import create_client
from yutto.utils.functional import as_sync


def test_build_user_space_params_matches_browser_request():
    wbi_img = WbiImg(img_key="a" * 32, sub_key="b" * 32)
    params = _build_user_space_params(MId("441167301"), pn=1, ps=40, wbi_img=wbi_img)

    assert params["mid"] == MId("441167301")
    assert params["ps"] == 40
    assert params["pn"] == 1
    assert params["tid"] == 0
    assert params["order"] == "pubdate"
    assert params["special_type"] == ""
    assert params["index"] == 0
    assert params["keyword"] == ""
    assert params["order_avoided"] == "true"
    assert params["platform"] == "web"
    assert params["web_location"] == SPACE_ARC_WEB_LOCATION
    assert params["dm_img_inter"] == DM_IMG_INTER
    assert params["x-bili-device-req-json"] == X_BILI_DEVICE_REQ_JSON
    assert "w_rid" in params
    assert "wts" in params


@as_sync
async def test_ensure_web_identity_sets_browser_cookies_once(monkeypatch: pytest.MonkeyPatch):
    import yutto.api.web_identity as web_identity

    calls: list[str] = []

    class FakeFetcher:
        @staticmethod
        async def fetch_json(scope: Any, url: str, **kwargs: Any) -> Any:
            calls.append(url)
            return Success({"code": 0, "data": {"b_3": "buvid3-value", "b_4": "buvid4-value"}})

        @staticmethod
        async def post_json(scope: Any, url: str, **kwargs: Any) -> Any:
            calls.append(url)
            return Success({"code": 0, "data": {"ticket": "ticket-value", "created_at": 100, "ttl": 200}})

        @staticmethod
        async def touch_url(scope: Any, url: str) -> Any:
            calls.append(url)
            return Success(None)

    class FakeSession:
        def __init__(self) -> None:
            self.cookies: dict[str, str] = {}

        def set_cookie(self, name: str, value: str, url: str = "https://www.bilibili.com/") -> None:
            self.cookies[name] = value

        def cookie(self, name: str, url: str = "https://www.bilibili.com/") -> str | None:
            return self.cookies.get(name)

    monkeypatch.setattr(web_identity, "Fetcher", FakeFetcher)
    session = FakeSession()
    scope = ExecutionScope(cast("Any", session))

    await web_identity.ensure_web_identity(scope)
    await web_identity.ensure_web_identity(scope)

    assert session.cookies["buvid3"] == "buvid3-value"
    assert session.cookies["buvid4"] == "buvid4-value"
    assert session.cookies["bili_ticket"] == "ticket-value"
    assert session.cookies["bili_ticket_expires"] == "300"
    assert "b_nut" in session.cookies
    assert calls == [web_identity.BILI_SPI_API, web_identity.BILI_TICKET_API]


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_space_all_videos_avids():
    mid = MId("100969474")
    async with create_client() as client:
        scope = ExecutionScope(client)
        all_avid = await get_user_space_all_videos_avids(scope, mid=mid)
        assert len(all_avid) > 0
        assert AId("371660125") in all_avid or BvId("BV1vZ4y1M7mQ") in all_avid


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_name():
    mid = MId("100969474")
    async with create_client() as client:
        scope = ExecutionScope(client)
        username = await get_user_name(scope, mid=mid)
        assert username == "时雨千陌"


@pytest.mark.api
@as_sync
async def test_get_favourite_info():
    fid = FId("1306978874")
    async with create_client() as client:
        scope = ExecutionScope(client)
        fav_info = await get_favourite_info(scope, fid=fid)
        assert fav_info["fid"] == fid
        assert fav_info["title"] == "Test"


@pytest.mark.api
@as_sync
async def test_get_favourite_avids():
    fid = FId("1306978874")
    async with create_client() as client:
        scope = ExecutionScope(client)
        avids = await get_favourite_avids(scope, fid=fid)
        assert AId("456782499") in avids or BvId("BV1o541187Wh") in avids


@pytest.mark.api
@as_sync
async def test_all_favourites():
    mid = MId("100969474")
    async with create_client() as client:
        scope = ExecutionScope(client)
        fav_list = await get_all_favourites(scope, mid=mid)
        assert {"fid": FId("1306978874"), "title": "Test"} in fav_list


@pytest.mark.api
@as_sync
async def test_get_medialist_avids():
    series_id = SeriesId("1947439")
    mid = MId("100969474")
    async with create_client() as client:
        scope = ExecutionScope(client)
        avids = await get_medialist_avids(scope, series_id=series_id, mid=mid)
        assert avids == [BvId("BV1Y441167U2"), BvId("BV1vZ4y1M7mQ")]


@pytest.mark.api
@as_sync
async def test_get_medialist_title():
    series_id = SeriesId("1947439")
    async with create_client() as client:
        scope = ExecutionScope(client)
        title = await get_medialist_title(scope, series_id=series_id)
        assert title == "一个小视频列表～"
