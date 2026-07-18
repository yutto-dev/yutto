from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.space import get_all_favourites, get_favourite_items, get_user_name
from yutto.core.operation import notify_episode_listed
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.extractor.utils.favourite import normalize_favourite_video_item
from yutto.types import MId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.space import FavouriteVideoData
    from yutto.api.ugc_video import UgcVideoList
    from yutto.types import AvId, ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class UserAllFavouritesExtractor(BatchExtractor):
    """用户所有收藏夹"""

    REGEX_FAV_ALL = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist$")

    mid: MId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_FAV_ALL.match(url):
            self.mid = MId(match_obj.group("mid"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[ResolvableEpisode | None]:
        username = await get_user_name(ctx, client, self.mid)
        Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

        all_episodes: list[ResolvableEpisode | None] = []

        for fav in await get_all_favourites(ctx, client, self.mid):
            series_title = fav["title"]
            fid = fav["fid"]
            favourite_videos = await get_favourite_items(ctx, client, fid)
            avids = [favourite_video["avid"] for favourite_video in favourite_videos]

            # 逐视频解析完成即构建分集并推流（notify_episode_listed），收藏夹内按 index 重排。
            # 回调在本轮循环内就被消费；循环变量经默认参数绑定（B023）。
            episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

            async def build_episodes(
                index: int,
                _avid: AvId,
                ugc_video_list: UgcVideoList | None,
                *,
                _favourite_videos: list[FavouriteVideoData] = favourite_videos,
                _series_title: str = series_title,
                _episodes_by_index: dict[int, list[ResolvableEpisode]] = episodes_by_index,
            ) -> None:
                if ugc_video_list is None:
                    return
                favourite_video = _favourite_videos[index]
                # 优先使用收藏夹 API 返回的人工标题；失效视频 title 为空时退回到 ugc 接口标题
                favourite_title = favourite_video["title"] or ugc_video_list["title"]
                is_single_page_video = len(ugc_video_list["pages"]) == 1
                built: list[ResolvableEpisode] = []
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
                            "series_title": _series_title,
                            "pubdate": ugc_video_list["pubdate"],
                        },
                        auto_subpath_template,
                        display_group=display_group,
                    )
                    notify_episode_listed(episode)
                    await asyncio.sleep(0)
                    built.append(episode)
                _episodes_by_index[index] = built

            await resolve_ugc_video_lists(
                ctx,
                client,
                avids,
                publication_time_filter=options["publication_time_filter"],
                on_resolved=build_episodes,
            )
            all_episodes.extend(episode for index in range(len(avids)) for episode in episodes_by_index.get(index, []))

        return all_episodes
