import argparse
import asyncio
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.api.space import get_uploader_name, get_uploader_space_all_videos_avids
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class UploaderAllVideosExtractor(BatchExtractor):
    """UP 主个人空间全部视频"""

    REGEX_SPACE = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)(/video)?")

    mid: MId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_SPACE.match(url):
            self.mid = MId(match_obj.group("mid"))
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]:
        username = await get_uploader_name(session, self.mid)
        Logger.custom(username, Badge("UP 主投稿视频", fore="black", back="cyan"))

        acg_video_list = [
            acg_video_item
            for avid in await get_uploader_space_all_videos_avids(session, self.mid)
            for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
        ]

        return [
            self._parse_episodes_data(
                session,
                args,
                username,
                i,
                acg_video_item,
            )
            for i, acg_video_item in enumerate(acg_video_list)
        ]

    async def _parse_episodes_data(
        self,
        session: aiohttp.ClientSession,
        args: argparse.Namespace,
        username: str,
        i: int,
        acg_video_item: AcgVideoListItem,
    ) -> Optional[tuple[int, EpisodeData]]:
        try:
            _, title, pubdate = await asyncio.gather(
                Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                get_acg_video_title(session, acg_video_item["avid"]),
                get_acg_video_pubdate(session, acg_video_item["avid"]),
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
                        "pubdate": pubdate,
                    },
                    "{username}的全部投稿视频/{title}/{name}",
                ),
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
