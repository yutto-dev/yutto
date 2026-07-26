from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from yutto.api.cheese import get_cheese_list, get_season_id_by_episode_id
from yutto.core.operation import emit_download_report
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_cheese_episode
from yutto.extractor.outcome import ResolveOutcome
from yutto.input_parser import parse_episodes_selection
from yutto.types import EpisodeId, SeasonId

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.extractor._abc import EpisodeListedCallback, ExtractorResolveOutcome
    from yutto.types import ExtractorOptions


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

    async def _parse_ids(self, scope: ExecutionScope):
        if "episode_id" in self._match_result.groupdict().keys():
            episode_id = EpisodeId(self._match_result.group("episode_id"))
            self.season_id = await get_season_id_by_episode_id(scope, episode_id)
        else:
            self.season_id = SeasonId(self._match_result.group("season_id"))

    async def extract(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ExtractorResolveOutcome:
        await self._parse_ids(scope)

        cheese_list = await get_cheese_list(scope, self.season_id)
        emit_download_report(cheese_list["title"], badge="课程")
        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(cheese_list["pages"]))
        cheese_list["pages"] = list(filter(lambda item: item["id"] in episodes, cheese_list["pages"]))
        return ResolveOutcome(
            items=tuple(
                make_cheese_episode(
                    scope,
                    cheese_item["episode_id"],
                    cheese_item,
                    options,
                    {
                        "title": cheese_list["title"],
                    },
                    "{title}/{name}",
                )
                for cheese_item in cheese_list["pages"]
            )
        )
