from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from yutto._typing import EpisodeData, EpisodeId, SeasonId
from yutto.api.cheese import get_cheese_list, get_season_id_by_episode_id
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_cheese_data
from yutto.parser import parse_episodes_selection
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext


class CheeseBatchExtractor(BatchExtractor):
    """课程全集"""

    REGEX_EP = re.compile(r"https?://www\.bilibili\.com/cheese/play/ep(?P<episode_id>\d+)")
    REGEX_SS = re.compile(r"https?://www\.bilibili\.com/cheese/play/ss(?P<season_id>\d+)")

    #  REGEX_EP_ID = re.compile(r"ep(?P<episode_id>\d+)")
    #  REGEX_SS_ID = re.compile(r"ss(?P<season_id>\d+)")

    _match_result: re.Match[Any]
    season_id: SeasonId

    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        # TODO 和番剧的快捷方式冲突，课程中暂时放弃快捷方式特性
        # if match_obj := self.REGEX_EP_ID.match(id):
        #     url = f"https://www.bilibili.com/cheese/play/ep{match_obj.group('episode_id')}"
        #     matched = True
        # elif match_obj := self.REGEX_SS_ID.match(id):
        #     url = f"https://www.bilibili.com/cheese/play/ss{match_obj.group('season_id')}"
        #     matched = True
        return matched, url

    def match(self, url: str) -> bool:
        if (match_obj := self.REGEX_SS.match(url)) or (match_obj := self.REGEX_EP.match(url)):
            self._match_result = match_obj
            return True
        else:
            return False

    async def _parse_ids(self, ctx: FetcherContext, client: httpx.AsyncClient):
        if "episode_id" in self._match_result.groupdict().keys():
            episode_id = EpisodeId(self._match_result.group("episode_id"))
            self.season_id = await get_season_id_by_episode_id(ctx, client, episode_id)
        else:
            self.season_id = SeasonId(self._match_result.group("season_id"))

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        await self._parse_ids(ctx, client)

        cheese_list = await get_cheese_list(ctx, client, self.season_id)
        Logger.custom(cheese_list["title"], Badge("课程", fore="black", back="cyan"))
        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(cheese_list["pages"]))
        cheese_list["pages"] = list(filter(lambda item: item["id"] in episodes, cheese_list["pages"]))
        return [
            CoroutineWrapper(
                extract_cheese_data(
                    ctx,
                    client,
                    cheese_item["episode_id"],
                    cheese_item,
                    options,
                    {
                        "title": cheese_list["title"],
                    },
                    "{title}/{name}",
                )
            )
            for cheese_item in cheese_list["pages"]
        ]
