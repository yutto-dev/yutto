from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto.api.space import get_all_favourites, get_favourite_items, get_user_name
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.extractor.utils.favourite import normalize_favourite_video_item
from yutto.types import MId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoListItem
    from yutto.types import ExtractorOptions, ResolvableEpisode
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

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int, str, str, str | None]] = []

        for fav in await get_all_favourites(ctx, client, self.mid):
            series_title = fav["title"]
            fid = fav["fid"]
            favourite_videos = await get_favourite_items(ctx, client, fid)
            avids = [favourite_video["avid"] for favourite_video in favourite_videos]
            ugc_video_lists = await resolve_ugc_video_lists(
                ctx,
                client,
                avids,
                publication_time_filter=options["publication_time_filter"],
            )
            for favourite_video, ugc_video_list in zip(favourite_videos, ugc_video_lists, strict=True):
                if ugc_video_list is None:
                    continue
                # 优先使用收藏夹 API 返回的人工标题；失效视频 title 为空时退回到 ugc 接口标题
                favourite_title = favourite_video["title"] or ugc_video_list["title"]
                is_single_page_video = len(ugc_video_list["pages"]) == 1
                for ugc_video_item in ugc_video_list["pages"]:
                    resolved_video_item, auto_subpath_template, display_group = normalize_favourite_video_item(
                        ugc_video_item,
                        favourite_title,
                        is_single_page_video=is_single_page_video,
                    )
                    ugc_video_info_list.append(
                        (
                            resolved_video_item,
                            favourite_title,
                            ugc_video_list["pubdate"],
                            series_title,
                            auto_subpath_template,
                            display_group,
                        )
                    )

        return [
            make_ugc_video_episode(
                ctx,
                client,
                ugc_video_item["avid"],
                ugc_video_item,
                options,
                {
                    "title": title,
                    "username": username,
                    "series_title": series_title,
                    "pubdate": pubdate,
                },
                auto_subpath_template,
                display_group=display_group,
            )
            for ugc_video_item, title, pubdate, series_title, auto_subpath_template, display_group in ugc_video_info_list
        ]
