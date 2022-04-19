import aiohttp
import pytest

from yutto._typing import BvId, MId, SeriesId
from yutto.api.collection import get_collection_details
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


@pytest.mark.api
@as_sync
async def test_get_collection_details():
    # 测试页面：https://space.bilibili.com/361469957/channel/collectiondetail?sid=23195&ctype=0
    series_id = SeriesId("23195")
    mid = MId("361469957")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        collection_details = await get_collection_details(session, series_id=series_id, mid=mid)
        title = collection_details["title"]
        avids = [page["avid"] for page in collection_details["pages"]]
        assert title == "算法入门【Go语言】"
        assert BvId("BV1xy4y1G7tz") in avids
        assert BvId("BV1k34y1S71P") in avids
