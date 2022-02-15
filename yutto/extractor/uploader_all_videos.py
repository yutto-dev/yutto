import argparse
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, MId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list
from yutto.api.space import get_uploader_name, get_uploader_space_all_videos_avids
from yutto.exceptions import NotFoundError
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
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        username = await get_uploader_name(session, self.mid)
        Logger.custom(username, Badge("UP 主投稿视频", fore="black", back="cyan"))

        acg_video_info_list: list[tuple[AcgVideoListItem, str, str]] = []
        for avid in await get_uploader_space_all_videos_avids(session, self.mid):
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
                    "title": title,
                    "username": username,
                    "pubdate": pubdate,
                },
                "{username}的全部投稿视频/{title}/{name}",
            )
            for acg_video_item, title, pubdate in acg_video_info_list
        ]
