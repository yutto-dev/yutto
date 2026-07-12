from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.space import get_favourite_info, get_favourite_items, get_user_name
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.extractor.utils.favourite import normalize_favourite_video_item
from yutto.types import FId, MId
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoListItem
    from yutto.types import EpisodeData, ExtractorOptions
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
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        username, favourite_info = await asyncio.gather(
            get_user_name(ctx, client, self.mid),
            get_favourite_info(ctx, client, self.fid),
        )
        Logger.custom(favourite_info["title"], Badge("收藏夹", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int, str, str | None]] = []

        favourite_videos = await get_favourite_items(ctx, client, self.fid)
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
                        auto_subpath_template,
                        display_group,
                    )
                )

        return [
            CoroutineWrapper(
                extract_ugc_video_data(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        "title": title,
                        "username": username,
                        "series_title": favourite_info["title"],
                        "pubdate": pubdate,
                    },
                    auto_subpath_template,
                    display_group=display_group,
                )
            )
            for ugc_video_item, title, pubdate, auto_subpath_template, display_group in ugc_video_info_list
        ]
