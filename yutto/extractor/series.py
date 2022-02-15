import argparse
import asyncio
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId, SeriesId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list
from yutto.api.space import (
    get_collection_avids,
    get_collection_title,
    get_medialist_avids,
    get_medialist_title,
    get_uploader_name,
)
from yutto.exceptions import NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class SeriesExtractor(BatchExtractor):
    """视频合集和视频列表"""

    REGEX_SERIES = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/seriesdetail\?sid=(?P<series_id>\d+)"
    )
    REGEX_MEDIA_LIST = re.compile(
        r"https?://www\.bilibili\.com/medialist/play/(?P<mid>\d+)\?business=space_series&business_id=(?P<series_id>\d+)"
    )
    REGEX_COLLECTIOMS = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/collectiondetail\?sid=(?P<series_id>\d+)"
    )

    mid: MId
    series_id: SeriesId
    is_collection: bool

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_MEDIA_LIST.match(url))
            or (match_obj := self.REGEX_SERIES.match(url))
            or (match_obj := self.REGEX_COLLECTIOMS.match(url))
        ):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
            self.is_collection = True if self.REGEX_COLLECTIOMS.match(url) else False
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        # 视频合集
        if self.is_collection:
            username, series_title = await asyncio.gather(
                get_uploader_name(session, self.mid),
                get_collection_title(session, self.series_id),
            )
            Logger.custom(series_title, Badge("视频合集", fore="black", back="cyan"))

            acg_video_info_list: list[tuple[AcgVideoListItem, str, str]] = []
            for avid in await get_collection_avids(session, self.series_id):
                try:
                    acg_video_list = await get_acg_video_list(session, avid)
                    await Fetcher.touch_url(session, avid.to_url())
                    for acg_video_item in acg_video_list["pages"]:
                        acg_video_info_list.append(
                            (
                                acg_video_item,
                                acg_video_list["title"],
                                acg_video_list["pubdate"],
                            )
                        )
                except NotFoundError as e:
                    Logger.error(e.message)
                    continue
        # 视频列表
        else:
            username, series_title = await asyncio.gather(
                get_uploader_name(session, self.mid), get_medialist_title(session, self.series_id)
            )
            Logger.custom(series_title, Badge("视频列表", fore="black", back="cyan"))

            acg_video_info_list: list[tuple[AcgVideoListItem, str, str]] = []
            for avid in await get_medialist_avids(session, self.series_id):
                try:
                    acg_video_list = await get_acg_video_list(session, avid)
                    await Fetcher.touch_url(session, avid.to_url())
                    for acg_video_item in acg_video_list["pages"]:
                        acg_video_info_list.append(
                            (
                                acg_video_item,
                                acg_video_list["title"],
                                acg_video_list["pubdate"],
                            )
                        )
                except NotFoundError as e:
                    Logger.error(e.message)
                    continue

        return [
            extract_acg_video_data(
                session,
                acg_video_item["avid"],
                acg_video_item,
                args,
                {
                    "series_title": series_title,
                    "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                    "title": title,
                    "pubdate": pubdate,
                },
                "{series_title}/{title}/{name}",
            )
            for acg_video_item, title, pubdate in acg_video_info_list
        ]
