from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto.api.space import get_all_favourites, get_favourite_items, get_user_name
from yutto.api.ugc_video import get_ugc_video_list
from yutto.exceptions import NoAccessPermissionError, NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.types import MId
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.favourite import normalize_favourite_video_item
from yutto.utils.fetcher import Fetcher
from yutto.utils.filter import Filter

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoListItem
    from yutto.types import EpisodeData, ExtractorOptions
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
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        username = await get_user_name(ctx, client, self.mid)
        Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int, str, str, str | None]] = []

        for fav in await get_all_favourites(ctx, client, self.mid):
            series_title = fav["title"]
            fid = fav["fid"]
            for favourite_video in await get_favourite_items(ctx, client, fid):
                avid = favourite_video["avid"]
                try:
                    ugc_video_list = await get_ugc_video_list(ctx, client, avid)
                    if not Filter.verify_timer(ugc_video_list["pubdate"]):
                        Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                        continue
                    await Fetcher.touch_url(ctx, client, avid.to_url())
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
                except (NotFoundError, NoAccessPermissionError) as e:
                    Logger.error(e.message)
                    continue

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
                        "series_title": series_title,
                        "pubdate": pubdate,
                    },
                    auto_subpath_template,
                    display_group=display_group,
                )
            )
            for ugc_video_item, title, pubdate, series_title, auto_subpath_template, display_group in ugc_video_info_list
        ]
