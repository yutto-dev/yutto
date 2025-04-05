from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto._typing import EpisodeData, MId, SeriesId
from yutto.api.collection import get_collection_details
from yutto.api.space import get_user_name
from yutto.api.ugc_video import UgcVideoListItem, get_ugc_video_list
from yutto.exceptions import NoAccessPermissionError, NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.parser import parse_episodes_selection
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import Filter

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions


class CollectionExtractor(BatchExtractor):
    """视频合集"""

    REGEX_COLLECTION_LISTS = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<series_id>\d+)\?type=season"
    )
    # 订阅合集后，在个人空间的收藏夹页面
    REGEX_COLLECTION_FAV_PAGE: re.Pattern[str] = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<series_id>\d+)&ftype=collect"
    )
    REGEX_COLLECTIOM_LEGACY = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/collectiondetail\?sid=(?P<series_id>\d+)"
    )

    mid: MId
    series_id: SeriesId

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_COLLECTION_LISTS.match(url))
            or (match_obj := self.REGEX_COLLECTION_FAV_PAGE.match(url))
            or (match_obj := self.REGEX_COLLECTIOM_LEGACY.match(url))
        ):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        username, collection_details = await asyncio.gather(
            get_user_name(ctx, client, self.mid),
            get_collection_details(ctx, client, self.series_id, self.mid),
        )
        collection_title = collection_details["title"]
        Logger.custom(collection_title, Badge("视频合集", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int]] = []

        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(collection_details["pages"]))
        collection_details["pages"] = list(filter(lambda item: item["id"] in episodes, collection_details["pages"]))

        for item in collection_details["pages"]:
            try:
                avid = item["avid"]
                ugc_video_list = await get_ugc_video_list(ctx, client, avid)
                if not Filter.verify_timer(ugc_video_list["pubdate"]):
                    Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                    continue
                await Fetcher.touch_url(ctx, client, avid.to_url())
                if len(ugc_video_list["pages"]) != 1:
                    Logger.error(f"视频合集 {collection_title} 中的视频 {item['avid']} 包含多个视频！")
                for ugc_video_item in ugc_video_list["pages"]:
                    ugc_video_info_list.append(
                        (
                            ugc_video_item,
                            ugc_video_list["title"],
                            ugc_video_list["pubdate"],
                        )
                    )
            except (NotFoundError, NoAccessPermissionError) as e:
                Logger.error(e.message)
                continue

        return [
            CoroutineWrapper(
                extract_ugc_video_data(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        # TODO: 关于对于 id 的优化
                        # TODO: 关于对于 title 的优化（最好使用合集标题，而不是原来的视频标题）
                        "series_title": collection_title,
                        "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                        "title": title,
                        "pubdate": pubdate,
                    },
                    "{series_title}/{title}",
                )
            )
            for ugc_video_item, title, pubdate in ugc_video_info_list
        ]
