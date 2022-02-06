import argparse
import asyncio
from typing import Optional

import aiohttp

from yutto.api.acg_video import get_acg_video_pubdate, get_acg_video_title
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import SingleExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.processor.urlparser import regexp_acg_video_av, regexp_acg_video_bv
from yutto._typing import AId, AvId, BvId, EpisodeData
from yutto.utils.console.logger import Badge, Logger


class AcgVideoExtractor(SingleExtractor):
    """投稿视频单视频"""

    page: int
    avid: AvId

    def match(self, url: str) -> bool:
        if (match_obj := regexp_acg_video_av.match(url)) or (match_obj := regexp_acg_video_bv.match(url)):
            self.page: int = 1
            if "aid" in match_obj.groupdict().keys():
                self.avid = AId(match_obj.group("aid"))
            else:
                self.avid = BvId(match_obj.group("bvid"))
            if match_obj.group("page") is not None:
                self.page = int(match_obj.group("page"))
            return True
        else:
            return False

    async def extract(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> Optional[EpisodeData]:
        title, pubdate = await asyncio.gather(
            get_acg_video_title(session, self.avid),
            get_acg_video_pubdate(session, self.avid),
        )
        Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))
        try:
            return await extract_acg_video_data(
                session,
                self.avid,
                self.page,
                None,
                args,
                {"title": title, "pubdate": pubdate},
                "{title}",
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
