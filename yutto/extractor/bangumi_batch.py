import argparse
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, EpisodeId, MediaId, SeasonId
from yutto.api.bangumi import (
    get_bangumi_list,
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_bangumi_data
from yutto.processor.selector import parse_episodes_selection
from yutto.utils.console.logger import Badge, Logger


class BangumiBatchExtractor(BatchExtractor):
    """番剧全集"""

    REGEX_MD = re.compile(r"https?://www\.bilibili\.com/bangumi/media/md(?P<media_id>\d+)")
    REGEX_EP = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")
    REGEX_SS = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ss(?P<season_id>\d+)")

    REGEX_MD_ID = re.compile(r"md(?P<media_id>\d+)")
    REGEX_EP_ID = re.compile(r"ep(?P<episode_id>\d+)")
    REGEX_SS_ID = re.compile(r"ss(?P<season_id>\d+)")

    _match_result: re.Match[Any]
    season_id: SeasonId

    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        if match_obj := self.REGEX_MD_ID.match(id):
            url = f"https://www.bilibili.com/bangumi/media/md{match_obj.group('media_id')}"
            matched = True
        elif match_obj := self.REGEX_EP_ID.match(id):
            url = f"https://www.bilibili.com/bangumi/play/ep{match_obj.group('episode_id')}"
            matched = True
        elif match_obj := self.REGEX_SS_ID.match(id):
            url = f"https://www.bilibili.com/bangumi/play/ss{match_obj.group('season_id')}"
            matched = True
        return matched, url

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_MD.match(url))
            or (match_obj := self.REGEX_SS.match(url))
            or (match_obj := self.REGEX_EP.match(url))
        ):
            self._match_result = match_obj
            return True
        else:
            return False

    async def _parse_ids(self, session: aiohttp.ClientSession):
        if "episode_id" in self._match_result.groupdict().keys():
            episode_id = EpisodeId(self._match_result.group("episode_id"))
            self.season_id = await get_season_id_by_episode_id(session, episode_id)
        elif "season_id" in self._match_result.groupdict().keys():
            self.season_id = SeasonId(self._match_result.group("season_id"))
        else:
            media_id = MediaId(self._match_result.group("media_id"))
            self.season_id = await get_season_id_by_media_id(session, media_id)

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        await self._parse_ids(session)

        bangumi_list = await get_bangumi_list(session, self.season_id)
        Logger.custom(bangumi_list["title"], Badge("番剧", fore="black", back="cyan"))
        # 如果没有 with_section 则不需要专区内容
        bangumi_list["pages"] = list(
            filter(lambda item: args.with_section or not item["is_section"], bangumi_list["pages"])
        )
        # 选集过滤
        episodes = parse_episodes_selection(args.episodes, len(bangumi_list["pages"]))
        bangumi_list["pages"] = list(filter(lambda item: item["id"] in episodes, bangumi_list["pages"]))
        return [
            extract_bangumi_data(
                session,
                bangumi_item["episode_id"],
                bangumi_item,
                args,
                {
                    "title": bangumi_list["title"],
                },
                "{title}/{name}",
            )
            for bangumi_item in bangumi_list["pages"]
        ]
