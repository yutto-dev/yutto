import argparse
import re
from typing import Optional

import aiohttp

from yutto._typing import EpisodeData, EpisodeId
from yutto.api.bangumi import get_bangumi_title, get_season_id_by_episode_id
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import extract_bangumi_data
from yutto.utils.console.logger import Badge, Logger


class BangumiExtractor(SingleExtractor):
    """番剧单话"""

    REGEX_EP = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")

    REGEX_EP_ID = re.compile(r"ep(?P<episode_id>\d+)")

    episode_id: EpisodeId

    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        if match_obj := self.REGEX_EP_ID.match(id):
            url = f"https://www.bilibili.com/bangumi/play/ep{match_obj.group('episode_id')}"
            matched = True
        return matched, url

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_EP.match(url):
            self.episode_id = EpisodeId(match_obj.group("episode_id"))
            return True
        else:
            return False

    async def extract(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> Optional[EpisodeData]:
        season_id = await get_season_id_by_episode_id(session, self.episode_id)
        title = await get_bangumi_title(session, season_id)
        Logger.custom(title, Badge("番剧", fore="black", back="cyan"))
        try:
            return await extract_bangumi_data(
                session,
                self.episode_id,
                None,
                args,
                {"title": title},
                "{name}",
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
