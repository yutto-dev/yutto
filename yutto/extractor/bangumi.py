import argparse
from typing import Optional

import aiohttp

from yutto.api.bangumi import get_bangumi_title, get_season_id_by_episode_id
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import extract_bangumi_data
from yutto.processor.urlparser import regexp_bangumi_ep
from yutto._typing import EpisodeData, EpisodeId
from yutto.utils.console.logger import Badge, Logger


class BangumiExtractor(SingleExtractor):
    """番剧单话"""

    episode_id: EpisodeId

    def match(self, url: str) -> bool:
        if match_obj := regexp_bangumi_ep.match(url):
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
