from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yutto.api.space import get_user_name, get_user_space_all_videos_avids
from yutto.core.operation import notify_episode_listed
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.types import MId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.types import AvId, ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class UserAllUgcVideosExtractor(BatchExtractor):
    """UP 主个人空间全部投稿视频"""

    REGEX_SPACE = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)(/video)?")

    mid: MId

    def match(self, url: str) -> bool:
        if match_obj := self.REGEX_SPACE.match(url):
            self.mid = MId(match_obj.group("mid"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[ResolvableEpisode | None]:
        username = await get_user_name(ctx, client, self.mid)
        Logger.custom(username, Badge("UP 主投稿视频", fore="black", back="cyan"))

        publication_time_filter = options["publication_time_filter"]
        avids = await get_user_space_all_videos_avids(
            ctx,
            client,
            self.mid,
            pubdate_filter=publication_time_filter.matches,
            stop_before_timestamp=publication_time_filter.start_timestamp,
        )

        # 逐视频解析完成即构建分集并推流（notify_episode_listed），最终按 index 重排。
        episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

        def build_episodes(index: int, _avid: AvId, ugc_video_list: UgcVideoList | None) -> None:
            if ugc_video_list is None:
                return
            built: list[ResolvableEpisode] = []
            for ugc_video_item in ugc_video_list["pages"]:
                episode = make_ugc_video_episode(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        "title": ugc_video_list["title"],
                        "username": username,
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "{username}的全部投稿视频/{title}/{name}",
                )
                notify_episode_listed(episode)
                built.append(episode)
            episodes_by_index[index] = built

        await resolve_ugc_video_lists(
            ctx,
            client,
            avids,
            publication_time_filter=publication_time_filter,
            on_resolved=build_episodes,
        )
        return [episode for index in range(len(avids)) for episode in episodes_by_index.get(index, [])]
