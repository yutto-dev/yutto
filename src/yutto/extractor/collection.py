from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.api.collection import get_collection_details
from yutto.api.space import get_user_name
from yutto.core.operation import notify_episode_listed
from yutto.extractor._abc import BatchExtractor
from yutto.extractor.common import make_ugc_video_episode
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.input_parser import parse_episodes_selection
from yutto.types import MId, SeriesId
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.types import AvId, ExtractorOptions, ResolvableEpisode
    from yutto.utils.fetcher import FetcherContext


class CollectionExtractor(BatchExtractor):
    """视频合集"""

    REGEX_COLLECTION_LISTS = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<series_id>\d+)\?type=season"
    )
    # 订阅合集后，在个人空间的收藏夹页面
    REGEX_COLLECTION_FAV_PAGE: re.Pattern[str] = re.compile(
        r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<series_id>\d+)&ftype=collect"
    )

    mid: MId
    series_id: SeriesId

    def match(self, url: str) -> bool:
        if (match_obj := self.REGEX_COLLECTION_LISTS.match(url)) or (
            match_obj := self.REGEX_COLLECTION_FAV_PAGE.match(url)
        ):
            self.mid = MId(match_obj.group("mid"))
            self.series_id = SeriesId(match_obj.group("series_id"))
            return True
        else:
            return False

    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, options: ExtractorOptions
    ) -> list[ResolvableEpisode | None]:
        username, collection_details = await asyncio.gather(
            get_user_name(ctx, client, self.mid),
            get_collection_details(ctx, client, self.series_id, self.mid),
        )
        collection_title = collection_details["title"]
        Logger.custom(collection_title, Badge("视频合集", fore="black", back="cyan"))

        # 选集过滤
        episodes = parse_episodes_selection(options["episodes"], len(collection_details["pages"]))
        collection_details["pages"] = list(filter(lambda item: item["id"] in episodes, collection_details["pages"]))

        items = collection_details["pages"]
        avids = [item["avid"] for item in items]

        # 逐视频解析完成即构建分集并推流（notify_episode_listed），最终按 index 重排。
        episodes_by_index: dict[int, list[ResolvableEpisode]] = {}

        def build_episodes(index: int, _avid: AvId, ugc_video_list: UgcVideoList | None) -> None:
            if ugc_video_list is None:
                return
            if len(ugc_video_list["pages"]) != 1:
                Logger.error(f"视频合集 {collection_title} 中的视频 {items[index]['avid']} 包含多个视频！")
            built: list[ResolvableEpisode] = []
            for ugc_video_item in ugc_video_list["pages"]:
                episode = make_ugc_video_episode(
                    ctx,
                    client,
                    ugc_video_item["avid"],
                    ugc_video_item,
                    options,
                    {
                        # TODO: 关于对于 id 的优化
                        # TODO: 关于对于 title 的优化（最好使用合集标题，而不是原来的视频标题）
                        "series_title": collection_title,
                        "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                        "title": ugc_video_list["title"],
                        "pubdate": ugc_video_list["pubdate"],
                    },
                    "{series_title}/{title}",
                )
                notify_episode_listed(episode)
                built.append(episode)
            episodes_by_index[index] = built

        await resolve_ugc_video_lists(
            ctx,
            client,
            avids,
            publication_time_filter=options["publication_time_filter"],
            on_resolved=build_episodes,
        )
        return [episode for index in range(len(avids)) for episode in episodes_by_index.get(index, [])]
