from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, TypedDict

from yutto.types import BvId, MId
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.types import AvId, SeriesId


class CollectionDetailsItem(TypedDict):
    id: int
    avid: AvId


class CollectionDetails(TypedDict):
    mid: MId
    title: str
    pages: list[CollectionDetailsItem]


async def _get_collection_page(
    scope: ExecutionScope,
    series_id: SeriesId,
    pn: int,
    ps: int,
) -> dict[str, Any]:
    api = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?season_id={series_id}&sort_reverse=false&page_num={pn}&page_size={ps}"
    collection_url = api.format(
        series_id=series_id,
        pn=pn,
        ps=ps,
    )
    json_data = unwrap_fetch_result(await Fetcher.fetch_json(scope, collection_url))
    return json_data["data"]


async def get_collection_details(
    scope: ExecutionScope,
    series_id: SeriesId,
) -> CollectionDetails:
    ps = 30

    data = await _get_collection_page(scope, series_id, 1, ps)

    mid = MId(str(data["meta"]["mid"]))
    title = data["meta"]["title"]
    total = math.ceil(data["page"]["total"] / ps)

    pages: list[CollectionDetailsItem] = []

    for pn in range(1, total + 1):
        if pn > 1:
            data = await _get_collection_page(scope, series_id, pn, ps)

        pages.extend(
            CollectionDetailsItem(
                id=ps * (pn - 1) + i + 1,
                avid=BvId(archive["bvid"]),
            )
            for i, archive in enumerate(data["archives"])
        )

    return CollectionDetails(mid=mid, title=title, pages=pages)
