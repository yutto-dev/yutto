from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from yutto._typing import EpisodeData, EpisodeId
from yutto.api.cheese import get_cheese_list, get_season_id_by_episode_id
from yutto.exceptions import (
    ErrorCode,
    HttpStatusError,
    NoAccessPermissionError,
    NotFoundError,
    UnSupportedTypeError,
)
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import extract_cheese_data
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext


class CheeseExtractor(SingleExtractor):
    """单课时"""

    REGEX_EP = re.compile(r"https?://www\.bilibili\.com/cheese/play/ep(?P<episode_id>\d+)")

    REGEX_EP_ID = re.compile(r"ep(?P<episode_id>\d+)")

    episode_id: EpisodeId

    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        # TODO 和番剧的快捷方式冲突，课程中暂时放弃快捷方式特性
        # if match_obj := self.REGEX_EP_ID.match(id):
        #     url = f"https://www.bilibili.com/cheese/play/ep{match_obj.group('episode_id')}"
        #     matched = True
        return matched, url

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_EP.match(url):
            self.episode_id = EpisodeId(match_obj.group("episode_id"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> CoroutineWrapper[EpisodeData | None] | None:
        season_id = await get_season_id_by_episode_id(ctx, client, self.episode_id)
        cheese_list = await get_cheese_list(ctx, client, season_id)
        Logger.custom(cheese_list["title"], Badge("课程", fore="black", back="cyan"))
        try:
            for cheese_item in cheese_list["pages"]:
                if cheese_item["episode_id"] == self.episode_id:
                    cheese_list_item = cheese_item
                    break
            else:
                Logger.error("在列表中未找到该剧集")
                sys.exit(ErrorCode.EPISODE_NOT_FOUND_ERROR.value)

            return CoroutineWrapper(
                extract_cheese_data(
                    ctx,
                    client,
                    self.episode_id,
                    cheese_list_item,
                    options,
                    {
                        "title": cheese_list["title"],
                    },
                    "{name}",
                )
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
