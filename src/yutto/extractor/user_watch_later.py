from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.space import get_watch_later_avids
from yutto.exceptions import NotLoginError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.outcome import ResolveOutcome
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.extractor._abc import EpisodeListedCallback
    from yutto.types import AvId, ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class UserWatchLaterExtractor(BatchExtractor):
    """用户稍后再看"""

    REGEX_WATCH_LATER_INDEX = re.compile(r"https?://www\.bilibili\.com/watchlater/?.*?$")
    REGEX_WATCH_LATER_LIST = re.compile(r"https?://www\.bilibili\.com/list/watchlater/?.*?$")

    def match(self, url: str) -> bool:
        if self.REGEX_WATCH_LATER_INDEX.match(url) or self.REGEX_WATCH_LATER_LIST.match(url):
            return True
        else:
            return False

    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        Logger.custom("当前用户", Badge("稍后再看", fore="black", back="cyan"))

        try:
            avid_list = await get_watch_later_avids(ctx, client)
        except NotLoginError as e:
            Logger.error(e.message)
            return ResolveOutcome(failures=(e,))

        # 逐视频解析完成即构建分集并通过显式回调推流，最终按 index 重排。
        episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

        async def build_episodes(index: int, _avid: AvId, ugc_video_list: UgcVideoList | None) -> None:
            if ugc_video_list is None:
                return
            built: list[ResolvableEpisode] = []
            for ugc_video_item in ugc_video_list["pages"]:
                episode = make_ugc_video_episode(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        "title": ugc_video_list["title"],
                        "username": "",
                        "series_title": "稍后再看",
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "稍后再看/{title}/{name}",
                )
                if on_item is not None:
                    await on_item(episode)
                else:
                    await asyncio.sleep(0)
                built.append(episode)
            episodes_by_index[index] = built

        batch_outcome = await resolve_ugc_video_lists(
            ctx,
            client,
            avid_list,
            publication_time_filter=options["publication_time_filter"],
            on_resolved=build_episodes,
        )
        return ResolveOutcome(
            items=tuple(episode for index in range(len(avid_list)) for episode in episodes_by_index.get(index, [])),
            failures=batch_outcome.failures,
        )
