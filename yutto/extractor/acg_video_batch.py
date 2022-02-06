import argparse
import asyncio
from typing import Any, Coroutine, Optional

import aiohttp

from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, UnSupportedTypeError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.processor.filter import parse_episodes
from yutto.processor.urlparser import regexp_acg_video_av, regexp_acg_video_bv
from yutto._typing import AId, AvId, BvId, EpisodeData
from yutto.utils.console.logger import Badge, Logger


class AcgVideoBatchExtractor(BatchExtractor):
    """投稿视频批下载"""

    avid: AvId

    def match(self, url: str) -> bool:
        if (match_obj := regexp_acg_video_av.match(url)) or (match_obj := regexp_acg_video_bv.match(url)):
            if "aid" in match_obj.groupdict().keys():
                self.avid = AId(match_obj.group("aid"))
            else:
                self.avid = BvId(match_obj.group("bvid"))
            return True
        else:
            return False

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]:
        title, pubdate, acg_video_list = await asyncio.gather(
            get_acg_video_title(session, self.avid),
            get_acg_video_pubdate(session, self.avid),
            get_acg_video_list(session, self.avid, with_metadata=args.with_metadata),
        )
        Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))

        # 选集过滤
        episodes = parse_episodes(args.episodes, len(acg_video_list))
        acg_video_list = list(filter(lambda item: item["id"] in episodes, acg_video_list))

        return [
            self._parse_episodes_data(
                session,
                self.avid,
                args,
                title,
                pubdate,
                i,
                acg_video_item,
            )
            for i, acg_video_item in enumerate(acg_video_list)
        ]

    async def _parse_episodes_data(
        self,
        session: aiohttp.ClientSession,
        avid: AvId,
        args: argparse.Namespace,
        title: str,
        pubdate: str,
        i: int,
        acg_video_item: AcgVideoListItem,
    ) -> Optional[tuple[int, EpisodeData]]:
        try:
            return (
                i,
                await extract_acg_video_data(
                    session,
                    avid,
                    i + 1,
                    acg_video_item,
                    args,
                    {"title": title, "pubdate": pubdate},
                    "{title}/{name}",
                ),
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
            Logger.error(e.message)
            return None
