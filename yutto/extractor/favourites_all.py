import argparse
import asyncio
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.api.space import get_all_favourites, get_favourite_avids, get_uploader_name
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class FavouritesAllExtractor(BatchExtractor):
    """用户单一收藏夹"""

    REGEX_FAV_ALL = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<fid>\d+)")

    mid: MId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_FAV_ALL.match(url):
            self.mid = MId(match_obj.group("mid"))
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]:
        username = await get_uploader_name(session, self.mid)
        Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

        acg_video_list = [
            (acg_video_item, fav["title"])
            for fav in await get_all_favourites(session, self.mid)
            for avid in await get_favourite_avids(session, fav["fid"])
            for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
        ]

        return [
            self._parse_episodes_data(
                session,
                args,
                username,
                series_title,
                i,
                acg_video_item,
            )
            for i, (acg_video_item, series_title) in enumerate(acg_video_list)
        ]

    async def _parse_episodes_data(
        self,
        session: aiohttp.ClientSession,
        args: argparse.Namespace,
        username: str,
        series_title: str,
        i: int,
        acg_video_item: AcgVideoListItem,
    ) -> Optional[tuple[int, EpisodeData]]:
        pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
        try:
            _, title = await asyncio.gather(
                Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                get_acg_video_title(session, acg_video_item["avid"]),
            )
            return (
                i,
                await extract_acg_video_data(
                    session,
                    acg_video_item["avid"],
                    i + 1,
                    acg_video_item,
                    args,
                    {
                        "title": title,
                        "username": username,
                        "series_title": series_title,
                        "pubdate": pubdate,
                    },
                    "{username}的收藏夹/{series_title}/{title}/{name}",
                ),
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
