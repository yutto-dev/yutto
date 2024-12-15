from __future__ import annotations

import pytest

from yutto._typing import AId, BvId, FId, MId, SeriesId
from yutto.api.space import (
    get_all_favourites,
    get_favourite_avids,
    get_favourite_info,
    get_medialist_avids,
    get_medialist_title,
    get_user_name,
    get_user_space_all_videos_avids,
)
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_space_all_videos_avids():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        all_avid = await get_user_space_all_videos_avids(ctx, client, mid=mid)
        assert len(all_avid) > 0
        assert AId("371660125") in all_avid or BvId("BV1vZ4y1M7mQ") in all_avid


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_name():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        username = await get_user_name(ctx, client, mid=mid)
        assert username == "时雨千陌"


@pytest.mark.api
@as_sync
async def test_get_favourite_info():
    fid = FId("1306978874")
    ctx = FetcherContext()
    async with create_client() as client:
        fav_info = await get_favourite_info(ctx, client, fid=fid)
        assert fav_info["fid"] == fid
        assert fav_info["title"] == "Test"


@pytest.mark.api
@as_sync
async def test_get_favourite_avids():
    fid = FId("1306978874")
    ctx = FetcherContext()
    async with create_client() as client:
        avids = await get_favourite_avids(ctx, client, fid=fid)
        assert AId("456782499") in avids or BvId("BV1o541187Wh") in avids


@pytest.mark.api
@as_sync
async def test_all_favourites():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        fav_list = await get_all_favourites(ctx, client, mid=mid)
        assert {"fid": FId("1306978874"), "title": "Test"} in fav_list


@pytest.mark.api
@as_sync
async def test_get_medialist_avids():
    series_id = SeriesId("1947439")
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        avids = await get_medialist_avids(ctx, client, series_id=series_id, mid=mid)
        assert avids == [BvId("BV1Y441167U2"), BvId("BV1vZ4y1M7mQ")]


@pytest.mark.api
@as_sync
async def test_get_medialist_title():
    series_id = SeriesId("1947439")
    ctx = FetcherContext()
    async with create_client() as client:
        title = await get_medialist_title(ctx, client, series_id=series_id)
        assert title == "一个小视频列表～"
