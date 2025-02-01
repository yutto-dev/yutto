from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING, TypedDict

from yutto._typing import AvId, BvId, MId, SeriesId
from yutto.utils.fetcher import Fetcher, FetcherContext

if TYPE_CHECKING:
    from httpx import AsyncClient


class CollectionDetailsItem(TypedDict):
    id: int
    title: str
    avid: AvId


class CollectionDetails(TypedDict):
    title: str
    pages: list[CollectionDetailsItem]


async def get_collection_details(
    ctx: FetcherContext, client: AsyncClient, series_id: SeriesId, mid: MId
) -> CollectionDetails:
    title, avids = await asyncio.gather(
        _get_collection_title(ctx, client, series_id),
        _get_collection_avids(ctx, client, series_id, mid),
    )
    return CollectionDetails(
        title=title,
        pages=[
            CollectionDetailsItem(
                id=i + 1,
                title="",  # TODO: 这里应该是合集内的标题，但目前没找到相关的 API
                avid=avid,
            )
            for i, avid in enumerate(avids)
        ],
    )


async def _get_collection_avids(ctx: FetcherContext, client: AsyncClient, series_id: SeriesId, mid: MId) -> list[AvId]:
    api = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid={mid}&season_id={series_id}&sort_reverse=false&page_num={pn}&page_size={ps}"
    ps = 30
    pn = 1
    total = 1
    all_avid: list[AvId] = []

    while pn <= total:
        space_videos_url = api.format(series_id=series_id, ps=ps, pn=pn, mid=mid)
        json_data = await Fetcher.fetch_json(ctx, client, space_videos_url)
        assert json_data is not None
        total = math.ceil(json_data["data"]["page"]["total"] / ps)
        pn += 1
        all_avid += [BvId(archives["bvid"]) for archives in json_data["data"]["archives"]]
    return all_avid


async def _get_collection_title(ctx: FetcherContext, client: AsyncClient, series_id: SeriesId) -> str:
    api = "https://api.bilibili.com/x/v1/medialist/info?type=8&biz_id={series_id}"
    json_data = await Fetcher.fetch_json(ctx, client, api.format(series_id=series_id))
    assert json_data is not None
    return json_data["data"]["title"]
