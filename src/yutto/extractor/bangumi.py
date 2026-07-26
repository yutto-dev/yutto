from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto.api.bangumi import get_bangumi_list, get_season_id_by_episode_id
from yutto.core.operation import ReportLevel, emit_download_report
from yutto.exceptions import (
    EpisodeNotFoundError,
    HttpStatusError,
    NoAccessPermissionError,
    NotFoundError,
    UnSupportedTypeError,
)
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import make_bangumi_episode
from yutto.extractor.outcome import ResolveOutcome
from yutto.types import EpisodeId

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.extractor._abc import ExtractorResolveOutcome
    from yutto.types import ExtractorOptions


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

    async def extract(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
    ) -> ExtractorResolveOutcome:
        season_id = await get_season_id_by_episode_id(scope, self.episode_id)
        bangumi_list = await get_bangumi_list(scope, season_id)
        emit_download_report(bangumi_list["title"], badge="番剧")
        try:
            for bangumi_item in bangumi_list["pages"]:
                if bangumi_item["episode_id"] == self.episode_id:
                    bangumi_list_item = bangumi_item
                    break
            else:
                raise EpisodeNotFoundError("在列表中未找到该剧集")

            return ResolveOutcome(
                items=(
                    make_bangumi_episode(
                        scope,
                        bangumi_list_item,
                        options,
                        {
                            "title": bangumi_list["title"],
                        },
                        "{name}",
                    ),
                )
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            emit_download_report(e.message, ReportLevel.ERROR)
            return ResolveOutcome(failures=(e,))
