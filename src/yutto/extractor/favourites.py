from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.space import get_favourite_info, get_favourite_items, get_user_name
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.outcome import ResolveOutcome
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.extractor.utils.favourite import normalize_favourite_video_item
from yutto.types import FId, MId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.extractor._abc import EpisodeListedCallback
    from yutto.types import AvId, ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class FavouritesExtractor(BatchExtractor):
    """用户单一收藏夹"""

    REGEX_FAV = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<fid>\d+)((&ftype=create)|$)")

    mid: MId
    fid: FId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_FAV.match(url):
            self.mid = MId(match_obj.group("mid"))
            self.fid = FId(match_obj.group("fid"))
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
        username, favourite_info = await asyncio.gather(
            get_user_name(ctx, client, self.mid),
            get_favourite_info(ctx, client, self.fid),
        )
        Logger.custom(favourite_info["title"], Badge("收藏夹", fore="black", back="cyan"))

        favourite_videos = await get_favourite_items(ctx, client, self.fid)
        avids = [favourite_video["avid"] for favourite_video in favourite_videos]

        # 每个视频解析完成即构建其分集并通过显式回调推流；完成顺序与收藏夹
        # 顺序无关，最终按 index 重排。
        episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

        async def build_episodes(index: int, _avid: AvId, ugc_video_list: UgcVideoList | None) -> None:
            if ugc_video_list is None:
                return
            favourite_video = favourite_videos[index]
            # 优先使用收藏夹 API 返回的人工标题；失效视频 title 为空时退回到 ugc 接口标题
            favourite_title = favourite_video["title"] or ugc_video_list["title"]
            is_single_page_video = len(ugc_video_list["pages"]) == 1
            episodes: list[ResolvableEpisode] = []
            for ugc_video_item in ugc_video_list["pages"]:
                resolved_video_item, auto_subpath_template, display_group = normalize_favourite_video_item(
                    ugc_video_item,
                    favourite_title,
                    is_single_page_video=is_single_page_video,
                )
                episode = make_ugc_video_episode(
                    ctx,
                    client,
                    resolved_video_item["avid"],
                    resolved_video_item,
                    options,
                    {
                        "title": favourite_title,
                        "username": username,
                        "series_title": favourite_info["title"],
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    auto_subpath_template,
                    display_group=display_group,
                )
                if on_item is not None:
                    await on_item(episode)
                else:
                    await asyncio.sleep(0)
                episodes.append(episode)
            episodes_by_index[index] = episodes

        batch_outcome = await resolve_ugc_video_lists(
            ctx,
            client,
            avids,
            publication_time_filter=options["publication_time_filter"],
            on_resolved=build_episodes,
        )
        return ResolveOutcome(
            items=tuple(episode for index in range(len(avids)) for episode in episodes_by_index.get(index, [])),
            failures=batch_outcome.failures,
        )
