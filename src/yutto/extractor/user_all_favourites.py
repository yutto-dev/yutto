from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto._typing import EpisodeData, MId
from yutto.api.space import get_all_favourites, get_favourite_avids, get_user_name
from yutto.api.ugc_video import UgcVideoListItem, get_ugc_video_list
from yutto.exceptions import NoAccessPermissionError, NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import Filter

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions


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

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int, str]] = []

        for fav in await get_all_favourites(ctx, client, self.mid):
            series_title = fav["title"]
            fid = fav["fid"]
            for avid in await get_favourite_avids(ctx, client, fid):
                try:
                    ugc_video_list = await get_ugc_video_list(ctx, client, avid)
                    if not Filter.verify_timer(ugc_video_list["pubdate"]):
                        Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                        continue
                    await Fetcher.touch_url(ctx, client, avid.to_url())
                    for ugc_video_item in ugc_video_list["pages"]:
                        ugc_video_info_list.append(
                            (
                                ugc_video_item,
                                ugc_video_list["title"],
                                ugc_video_list["pubdate"],
                                series_title,
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
                    "{username}的收藏夹/{series_title}/{title}/{name}",
                )
            )
            for ugc_video_item, title, pubdate, series_title in ugc_video_info_list
        ]
