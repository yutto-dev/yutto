import argparse
import asyncio
import re
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData, FavouriteMetaData, FId, MId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.api.space import get_favourite_avids, get_favourite_info, get_uploader_name
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import extract_acg_video_data
from yutto.processor.filter import parse_episodes
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher


class FavouritesExtractor(BatchExtractor):
    """用户所有收藏夹"""

    REGEX_FAV = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<fid>\d+)")

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
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]:
        username, favourite_info = await asyncio.gather(
            get_uploader_name(session, self.mid),
            get_favourite_info(session, self.fid),
        )
        Logger.custom(favourite_info["title"], Badge("收藏夹", fore="black", back="cyan"))

        acg_video_list = [
            acg_video_item
            for avid in await get_favourite_avids(session, self.fid)
            for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
        ]
        # 选集过滤
        episodes = parse_episodes(args.episodes, len(acg_video_list))
        acg_video_list = list(filter(lambda item: item["id"] in episodes, acg_video_list))

        return [
            self._parse_episodes_data(
                session,
                args,
                username,
                favourite_info,
                i,
                acg_video_item,
            )
            for i, acg_video_item in enumerate(acg_video_list)
        ]

    async def _parse_episodes_data(
        self,
        session: aiohttp.ClientSession,
        args: argparse.Namespace,
        username: str,
        favourite_info: FavouriteMetaData,
        i: int,
        acg_video_item: AcgVideoListItem,
    ) -> Optional[tuple[int, EpisodeData]]:
        try:
            # 在使用 SESSDATA 时，如果不去事先 touch 一下视频链接的话，是无法获取 episode_data 的
            # 至于为什么前面那俩（投稿视频页和番剧页）不需要额外 touch，因为在 get_redirected_url 阶段连接过了呀
            _, title, pubdate = await asyncio.gather(
                Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                get_acg_video_title(session, acg_video_item["avid"]),
                get_acg_video_pubdate(session, acg_video_item["avid"]),
            )
            return (
                i,
                await extract_acg_video_data(
                    session,
                    acg_video_item["avid"],
                    i + 1,
                    acg_video_item,
                    args,
                    {
                        "title": title,
                        "username": username,
                        "series_title": favourite_info["title"],
                        "pubdate": pubdate,
                    },
                    "{username}的收藏夹/{series_title}/{title}/{name}",
                ),
            )
        except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
            Logger.error(e.message)
            return None
