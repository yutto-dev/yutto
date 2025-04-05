from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto._typing import EpisodeData, MId, SeriesId
from yutto.api.space import get_medialist_avids, get_medialist_title, get_user_name
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


class SeriesExtractor(BatchExtractor):
    """视频列表"""

    REGEX_SERIES_LISTS = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<series_id>\d+)\?type=series")
    REGEX_SERIES_LEGACY: re.Pattern[str] = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/seriesdetail\?sid=(?P<series_id>\d+)"
    )
    REGEX_SERIES_PLAYLIST = re.compile(r"https?://www\.bilibili\.com/list/(?P<mid>\d+)\?sid=(?P<series_id>\d+)")

    mid: MId
    series_id: SeriesId

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_SERIES_LISTS.match(url))
            or (match_obj := self.REGEX_SERIES_LEGACY.match(url))
            or (match_obj := self.REGEX_SERIES_PLAYLIST.match(url))
        ):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        username, series_title = await asyncio.gather(
            get_user_name(ctx, client, self.mid), get_medialist_title(ctx, client, self.series_id)
        )
        Logger.custom(series_title, Badge("视频列表", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int]] = []
        for avid in await get_medialist_avids(ctx, client, self.series_id, self.mid):
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
                        "series_title": series_title,
                        "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                        "title": title,
                        "pubdate": pubdate,
                    },
                    "{series_title}/{title}/{name}",
                )
            )
            for ugc_video_item, title, pubdate in ugc_video_info_list
        ]
