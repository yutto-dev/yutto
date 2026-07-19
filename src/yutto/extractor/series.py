from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.space import get_medialist_avids, get_medialist_title, get_user_name
from yutto.extractor._abc import StreamingBatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.outcome import ResolveOutcome
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.types import MId, SeriesId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.extractor._abc import EpisodeListedCallback, ExtractorResolveOutcome
    from yutto.extractor.utils.batch import IndexedResolveItem
    from yutto.types import ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class SeriesExtractor(StreamingBatchExtractor):
    """视频列表"""

    REGEX_SERIES_LISTS = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<series_id>\d+)\?type=series")
    REGEX_SERIES_PLAYLIST = re.compile(r"https?://www\.bilibili\.com/list/(?P<mid>\d+)\?sid=(?P<series_id>\d+)")

    mid: MId
    series_id: SeriesId

    def match(self, url: str) -> bool:
        if (match_obj := self.REGEX_SERIES_LISTS.match(url)) or (match_obj := self.REGEX_SERIES_PLAYLIST.match(url)):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
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
    ) -> ExtractorResolveOutcome:
        username, series_title = await asyncio.gather(
            get_user_name(ctx, client, self.mid), get_medialist_title(ctx, client, self.series_id)
        )
        Logger.custom(series_title, Badge("视频列表", fore="black", back="cyan"))

        avids = await get_medialist_avids(ctx, client, self.series_id, self.mid)

        # 逐视频解析完成即构建分集并通过显式回调推流，最终按 index 重排。
        episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

        async def build_episodes(resolved: IndexedResolveItem[UgcVideoList]) -> None:
            index = resolved.index
            ugc_video_list = resolved.value
            built: list[ResolvableEpisode] = []
            for ugc_video_item in ugc_video_list["pages"]:
                episode = make_ugc_video_episode(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        "series_title": series_title,
                        "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                        "title": ugc_video_list["title"],
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "{series_title}/{title}/{name}",
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
            avids,
            publication_time_filter=options["publication_time_filter"],
            on_resolved=build_episodes,
        )
        return ResolveOutcome(
            items=tuple(episode for index in range(len(avids)) for episode in episodes_by_index.get(index, [])),
            failures=tuple(failure.error for failure in batch_outcome.failures),
        )
