from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto.api.space import get_watch_later_avids
from yutto.api.ugc_video import UgcVideoListItem, get_ugc_video_list
from yutto.exceptions import NoAccessPermissionError, NotFoundError, NotLoginError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import Filter

if TYPE_CHECKING:
    import httpx

    from yutto._typing import EpisodeData, ExtractorOptions


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
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        Logger.custom("当前用户", Badge("稍后再看", fore="black", back="cyan"))

        ugc_video_info_list: list[tuple[UgcVideoListItem, str, int, str]] = []

        try:
            avid_list = await get_watch_later_avids(ctx, client)
        except NotLoginError as e:
            Logger.error(e.message)
            return []

        for avid in avid_list:
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
                            "稍后再看",
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
                        "username": "",
                        "series_title": series_title,
                        "pubdate": pubdate,
                    },
                    "稍后再看/{title}/{name}",
                )
            )
            for ugc_video_item, title, pubdate, series_title in ugc_video_info_list
        ]
