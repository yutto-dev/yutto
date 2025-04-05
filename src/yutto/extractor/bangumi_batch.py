from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from yutto._typing import EpisodeData, EpisodeId, MediaId, SeasonId
from yutto.api.bangumi import (
    get_bangumi_list,
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_bangumi_data
from yutto.parser import parse_episodes_selection
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext


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

    async def _parse_ids(self, ctx: FetcherContext, client: httpx.AsyncClient):
        if "episode_id" in self._match_result.groupdict().keys():
            episode_id = EpisodeId(self._match_result.group("episode_id"))
            self.season_id = await get_season_id_by_episode_id(ctx, client, episode_id)
        elif "season_id" in self._match_result.groupdict().keys():
            self.season_id = SeasonId(self._match_result.group("season_id"))
        else:
            media_id = MediaId(self._match_result.group("media_id"))
            self.season_id = await get_season_id_by_media_id(ctx, client, media_id)

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        await self._parse_ids(ctx, client)

        bangumi_list = await get_bangumi_list(ctx, client, self.season_id)
        Logger.custom(bangumi_list["title"], Badge("番剧", fore="black", back="cyan"))
        # 如果没有 with_section 则不需要专区内容
        bangumi_list["pages"] = list(
            filter(lambda item: options["with_section"] or not item["is_section"], bangumi_list["pages"])
        )
        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(bangumi_list["pages"]))
        bangumi_list["pages"] = list(filter(lambda item: item["id"] in episodes, bangumi_list["pages"]))
        return [
            CoroutineWrapper(
                extract_bangumi_data(
                    ctx,
                    client,
                    bangumi_item,
                    options,
                    {
                        "title": bangumi_list["title"],
                    },
                    "{title}/{name}",
                )
            )
            for bangumi_item in bangumi_list["pages"]
        ]
