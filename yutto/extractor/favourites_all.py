import argparse
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list
from yutto.api.space import get_all_favourites, get_favourite_avids, get_uploader_name
from yutto.exceptions import NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class FavouritesAllExtractor(BatchExtractor):
    """用户所有收藏夹"""

    REGEX_FAV_ALL = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist")

    mid: MId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_FAV_ALL.match(url):
            self.mid = MId(match_obj.group("mid"))
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        username = await get_uploader_name(session, self.mid)
        Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

        acg_video_info_list: list[tuple[AcgVideoListItem, str, str, str]] = []

        for fav in await get_all_favourites(session, self.mid):
            series_title = fav["title"]
            fid = fav["fid"]
            for avid in await get_favourite_avids(session, fid):
                try:
                    acg_video_list = await get_acg_video_list(session, avid)
                    await Fetcher.touch_url(session, avid.to_url())
                    for acg_video_item in acg_video_list["pages"]:
                        acg_video_info_list.append(
                            (
                                acg_video_item,
                                acg_video_list["title"],
                                acg_video_list["pubdate"],
                                series_title,
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
                    "title": title,
                    "username": username,
                    "series_title": series_title,
                    "pubdate": pubdate,
                },
                "{username}的收藏夹/{series_title}/{title}/{name}",
            )
            for acg_video_item, title, pubdate, series_title in acg_video_info_list
        ]
