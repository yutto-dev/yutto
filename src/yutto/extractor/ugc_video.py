from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto._typing import AId, AvId, BvId, EpisodeData
from yutto.api.ugc_video import get_ugc_video_list
from yutto.exceptions import (
    HttpStatusError,
    NoAccessPermissionError,
    NotFoundError,
    UnSupportedTypeError,
)
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import extract_ugc_video_data
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import argparse

    import httpx

    from yutto.utils.fetcher import FetcherContext


class UgcVideoExtractor(SingleExtractor):
    """投稿视频单视频"""

    REGEX_AV = re.compile(r"https?://www\.bilibili\.com/video/av(?P<aid>\d+)/?(\?p=(?P<page>\d+))?")
    REGEX_BV = re.compile(r"https?://www\.bilibili\.com/video/(?P<bvid>(bv|BV)\w+)/?(\?p=(?P<page>\d+))?")

    REGEX_AV_ID = re.compile(r"av(?P<aid>\d+)(\?p=(?P<page>\d+))?")
    REGEX_BV_ID = re.compile(r"(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")

    REGEX_BV_SPECIAL_PAGE = re.compile(r"https?://www\.bilibili\.com/festival/.+(?P<bvid>(bv|BV)\w+)")

    page: int
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
            self.page: int = 1
            if "aid" in match_obj.groupdict().keys():
                self.avid = AId(match_obj.group("aid"))
            else:
                self.avid = BvId(match_obj.group("bvid"))
            if "page" in match_obj.groupdict() and match_obj.group("page") is not None:
                self.page = int(match_obj.group("page"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> CoroutineWrapper[EpisodeData | None] | None:
        try:
            ugc_video_list = await get_ugc_video_list(ctx, client, self.avid)
            self.avid = ugc_video_list["avid"]  # 当视频撞车时，使用新的 avid 替代原有 avid，见 #96
            Logger.custom(ugc_video_list["title"], Badge("投稿视频", fore="black", back="cyan"))
            return CoroutineWrapper(
                extract_ugc_video_data(
                    ctx,
                    client,
                    self.avid,
                    ugc_video_list["pages"][self.page - 1],
                    args,
                    {
                        "title": ugc_video_list["title"],
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "{title}",
                )
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
