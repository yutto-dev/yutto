from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto._typing import AId, AvId, BvId, EpisodeData
from yutto.api.ugc_video import get_ugc_video_list
from yutto.exceptions import NoAccessPermissionError, NotFoundError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.parser import parse_episodes_selection
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto._typing import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext


class UgcVideoBatchExtractor(BatchExtractor):
    """投稿视频批下载"""

    REGEX_AV = re.compile(r"https?://www\.bilibili\.com/video/av(?P<aid>\d+)/?")
    REGEX_BV = re.compile(r"https?://www\.bilibili\.com/video/(?P<bvid>(bv|BV)\w+)/?")

    REGEX_AV_ID = re.compile(r"av(?P<aid>\d+)(\?p=(?P<page>\d+))?")
    REGEX_BV_ID = re.compile(r"(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")

    REGEX_BV_SPECIAL_PAGE = re.compile(r"https?://www\.bilibili\.com/festival/.+(?P<bvid>(bv|BV)\w+)")

    avid: AvId

    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        if match_obj := self.REGEX_AV_ID.match(id):
            page: int = 1
            if match_obj.group("page") is not None:
                page = int(match_obj.group("page"))
            url = f"https://www.bilibili.com/video/av{match_obj.group('aid')}?p={page}"
            matched = True
        elif match_obj := self.REGEX_BV_ID.match(id):
            page: int = 1
            if match_obj.group("page") is not None:
                page = int(match_obj.group("page"))
            url = f"https://www.bilibili.com/video/{match_obj.group('bvid')}?p={page}"
            matched = True
        return matched, url

    def match(self, url: str) -> bool:
        if (
            (match_obj := self.REGEX_AV.match(url))
            or (match_obj := self.REGEX_BV.match(url))
            or (match_obj := self.REGEX_BV_SPECIAL_PAGE.match(url))
        ):
            if "aid" in match_obj.groupdict().keys():
                self.avid = AId(match_obj.group("aid"))
            else:
                self.avid = BvId(match_obj.group("bvid"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        try:
            ugc_video_list = await get_ugc_video_list(ctx, client, self.avid)
            Logger.custom(ugc_video_list["title"], Badge("投稿视频", fore="black", back="cyan"))
        except (NotFoundError, NoAccessPermissionError) as e:
            # 由于获取 info 时候也会因为视频不存在而报错，因此这里需要捕捉下
            Logger.error(e.message)
            return []

        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(ugc_video_list["pages"]))
        ugc_video_list["pages"] = list(filter(lambda item: item["id"] in episodes, ugc_video_list["pages"]))

        return [
            CoroutineWrapper(
                extract_ugc_video_data(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        "title": ugc_video_list["title"],
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "{title}/{name}",
                )
            )
            for ugc_video_item in ugc_video_list["pages"]
        ]
