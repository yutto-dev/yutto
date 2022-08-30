from __future__ import annotations

import argparse
import asyncio
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId, SeriesId
from yutto.api.collection import get_collection_details
from yutto.api.space import get_user_name
from yutto.api.ugc_video import UgcVideoListItem, get_ugc_video_list
from yutto.exceptions import NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.processor.selector import parse_episodes_selection
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class CollectionExtractor(BatchExtractor):
    """视频合集"""

    REGEX_COLLECTIOM = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/collectiondetail\?sid=(?P<series_id>\d+)"
    )
    REGEX_COLLECTION_MEDIA_LIST = re.compile(
        r"https?://www\.bilibili\.com/medialist/play/(?P<mid>\d+)\?business=space_collection&business_id=(?P<series_id>\d+)"
    )
    REGEX_COLLECTION_FAV_PAGE = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<series_id>\d+)&ftype=collect"
    )

    mid: MId
    series_id: SeriesId

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_COLLECTION_MEDIA_LIST.match(url))
            or (match_obj := self.REGEX_COLLECTIOM.match(url))
            or (match_obj := self.REGEX_COLLECTION_FAV_PAGE.match(url))
        ):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        username, collection_details = await asyncio.gather(
            get_user_name(session, self.mid),
            get_collection_details(session, self.series_id, self.mid),
        )
        collection_title = collection_details["title"]
        Logger.custom(collection_title, Badge("视频合集", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, str]] = []

        # 选集过滤
        episodes = parse_episodes_selection(args.episodes, len(collection_details["pages"]))
        collection_details["pages"] = list(filter(lambda item: item["id"] in episodes, collection_details["pages"]))

        for item in collection_details["pages"]:
            try:
                avid = item["avid"]
                ugc_video_list = await get_ugc_video_list(session, avid)
                await Fetcher.touch_url(session, avid.to_url())
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
            except NotFoundError as e:
                Logger.error(e.message)
                continue

        return [
            extract_ugc_video_data(
                session,
                ugc_video_item["avid"],
                ugc_video_item,
                args,
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
            for ugc_video_item, title, pubdate in ugc_video_info_list
        ]
