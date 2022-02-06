import aiohttp
import pytest

from yutto.api.space import (
    get_all_favourites,
    get_favourite_avids,
    get_favourite_info,
    get_medialist_avids,
    get_medialist_title,
    get_uploader_name,
    get_uploader_space_all_videos_avids,
    get_collection_title,
    get_collection_avids,
)
from yutto._typing import AId, BvId, FId, MId, SeriesId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


@pytest.mark.api
@as_sync
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
@as_sync
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


@pytest.mark.api
@as_sync
async def test_get_favourite_info():
    fid = FId("1306978874")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        fav_info = await get_favourite_info(session, fid=fid)
        assert fav_info["fid"] == fid
        assert fav_info["title"] == "Test"


@pytest.mark.api
@as_sync
async def test_get_favourite_avids():
    fid = FId("1306978874")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        avids = await get_favourite_avids(session, fid=fid)
        assert AId("456782499") in avids or BvId("BV1o541187Wh") in avids


@pytest.mark.api
@as_sync
async def test_all_favourites():
    mid = MId("100969474")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        fav_list = await get_all_favourites(session, mid=mid)
        assert {"fid": FId("1306978874"), "title": "Test"} in fav_list


@pytest.mark.api
@as_sync
async def test_get_medialist_avids():
    series_id = SeriesId("1947439")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        avids = await get_medialist_avids(session, series_id=series_id)
        assert avids == [BvId("BV1Y441167U2"), BvId("BV1vZ4y1M7mQ")]


@pytest.mark.api
@as_sync
async def test_get_medialist_title():
    series_id = SeriesId("1947439")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        title = await get_medialist_title(session, series_id=series_id)
        assert title == "一个小合集～"


@pytest.mark.api
@as_sync
async def test_get_collection_avids():
    # 测试页面：https://space.bilibili.com/361469957/channel/collectiondetail?sid=23195&ctype=0
    series_id = SeriesId("23195")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        avids = await get_collection_avids(session, series_id=series_id)
        assert BvId("BV1xy4y1G7tz") in avids
        assert BvId("BV1k34y1S71P") in avids


@pytest.mark.api
@as_sync
async def test_get_collection_title():
    # 测试页面：https://space.bilibili.com/361469957/channel/collectiondetail?sid=23195&ctype=0
    series_id = SeriesId("23195")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        title = await get_collection_title(session, series_id=series_id)
        assert title == "算法入门【Go语言】"
