import argparse
import asyncio
import sys
from typing import Any, Coroutine, Optional

import aiohttp

from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.api.bangumi import (
    BangumiListItem,
    get_bangumi_list,
    get_bangumi_title,
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.api.space import (
    get_all_favourites,
    get_collection_avids,
    get_collection_title,
    get_favourite_avids,
    get_favourite_info,
    get_medialist_avids,
    get_medialist_title,
    get_uploader_name,
    get_uploader_space_all_videos_avids,
)
from yutto.cli.get import fetch_acg_video_data, fetch_bangumi_data
from yutto.exceptions import ErrorCode, HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.processor.downloader import process_video_download
from yutto.processor.filter import parse_episodes
from yutto.processor.urlparser import (
    regexp_acg_video_av,
    regexp_acg_video_bv,
    regexp_bangumi_ep,
    regexp_bangumi_md,
    regexp_bangumi_ss,
    regexp_collection,
    regexp_favourite,
    regexp_favourite_all,
    regexp_medialist,
    regexp_series,
    regexp_space_all,
)
from yutto.typing import AId, BvId, EpisodeData, EpisodeId, FId, MediaId, MId, SeasonId, SeriesId
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


@as_sync
async def run(args: argparse.Namespace):
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        url: str = args.url
        url = await Fetcher.get_redirected_url(session, url)
        download_list: list[tuple[int, EpisodeData]] = []
        coroutine_list: list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]
        num_videos: int

        # 匹配为番剧
        if (
            (match_obj := regexp_bangumi_ep.match(url))
            or (match_obj := regexp_bangumi_ss.match(url))
            or (match_obj := regexp_bangumi_md.match(url))
        ):
            if "episode_id" in match_obj.groupdict().keys():
                episode_id = EpisodeId(match_obj.group("episode_id"))
                season_id = await get_season_id_by_episode_id(session, episode_id)
            elif "season_id" in match_obj.groupdict().keys():
                season_id = SeasonId(match_obj.group("season_id"))
            else:
                media_id = MediaId(match_obj.group("media_id"))
                season_id = await get_season_id_by_media_id(session, media_id)
            title, bangumi_list = await asyncio.gather(
                get_bangumi_title(session, season_id),
                get_bangumi_list(session, season_id, with_metadata=args.with_metadata),
            )
            Logger.custom(title, Badge("番剧", fore="black", back="cyan"))
            # 如果没有 with_section 则不需要专区内容
            bangumi_list = list(filter(lambda item: args.with_section or not item["is_section"], bangumi_list))
            # 选集过滤
            episodes = parse_episodes(args.episodes, len(bangumi_list))
            bangumi_list = list(filter(lambda item: item["id"] in episodes, bangumi_list))
            num_videos = len(bangumi_list)

            async def _parse_episodes_data_bangumi(
                i: int,
                bangumi_item: BangumiListItem,
            ) -> Optional[tuple[int, EpisodeData]]:
                try:
                    return (
                        i,
                        await fetch_bangumi_data(
                            session,
                            bangumi_item["episode_id"],
                            bangumi_item,
                            args,
                            {"title": title},
                            "{title}/{name}",
                        ),
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
                    Logger.error(e.message)
                    return None

            coroutine_list = [
                _parse_episodes_data_bangumi(i, bangumi_item) for i, bangumi_item in enumerate(bangumi_list)
            ]

        # 匹配为投稿视频
        elif (match_obj := regexp_acg_video_av.match(url)) or (match_obj := regexp_acg_video_bv.match(url)):
            if "aid" in match_obj.groupdict().keys():
                avid = AId(match_obj.group("aid"))
            else:
                avid = BvId(match_obj.group("bvid"))
            title, pubdate, acg_video_list = await asyncio.gather(
                get_acg_video_title(session, avid),
                get_acg_video_pubdate(session, avid),
                get_acg_video_list(session, avid, with_metadata=args.with_metadata),
            )
            Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))
            # 选集过滤
            episodes = parse_episodes(args.episodes, len(acg_video_list))
            acg_video_list = list(filter(lambda item: item["id"] in episodes, acg_video_list))
            num_videos = len(acg_video_list)

            async def _parse_episodes_data_acg_video(
                i: int,
                acg_video_item: AcgVideoListItem,
            ) -> Optional[tuple[int, EpisodeData]]:
                try:
                    return (
                        i,
                        await fetch_acg_video_data(
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

            coroutine_list = [
                _parse_episodes_data_acg_video(i, acg_video_item) for i, acg_video_item in enumerate(acg_video_list)
            ]

        # 匹配为收藏
        elif match_obj := regexp_favourite.match(url):
            mid = MId(match_obj.group("mid"))
            fid = FId(match_obj.group("fid"))
            username, favourite_info = await asyncio.gather(
                get_uploader_name(session, mid), get_favourite_info(session, fid)
            )
            Logger.custom(favourite_info["title"], Badge("收藏夹", fore="black", back="cyan"))

            acg_video_list = [
                acg_video_item
                for avid in await get_favourite_avids(session, fid)
                for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
            ]
            num_videos = len(acg_video_list)

            async def _parse_episodes_data_favourite(
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
                        await fetch_acg_video_data(
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

            coroutine_list = [
                _parse_episodes_data_favourite(i, acg_video_item) for i, acg_video_item in enumerate(acg_video_list)
            ]

        # 匹配为用户全部收藏
        elif match_obj := regexp_favourite_all.match(url):
            mid = MId(match_obj.group("mid"))
            username = await get_uploader_name(session, mid)
            Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

            acg_video_list = [
                (acg_video_item, fav["title"])
                for fav in await get_all_favourites(session, mid)
                for avid in await get_favourite_avids(session, fav["fid"])
                for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
            ]
            num_videos = len(acg_video_list)

            async def _parse_episodes_data_all_favourites(
                i: int,
                acg_video_item: AcgVideoListItem,
                series_title: str,
            ) -> Optional[tuple[int, EpisodeData]]:
                pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
                try:
                    _, title = await asyncio.gather(
                        Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                        get_acg_video_title(session, acg_video_item["avid"]),
                    )
                    return (
                        i,
                        await fetch_acg_video_data(
                            session,
                            acg_video_item["avid"],
                            i + 1,
                            acg_video_item,
                            args,
                            {"title": title, "username": username, "series_title": series_title, "pubdate": pubdate},
                            "{username}的收藏夹/{series_title}/{title}/{name}",
                        ),
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    return None

            coroutine_list = [
                _parse_episodes_data_all_favourites(i, acg_video_item, series_title)
                for i, (acg_video_item, series_title) in enumerate(acg_video_list)
            ]

        # 匹配为合集/视频列表
        elif (match_obj := regexp_medialist.match(url)) or (
            match_obj := regexp_series.match(url) or (match_obj := regexp_collection.match(url))
        ):
            mid = MId(match_obj.group("mid"))
            series_id = SeriesId(match_obj.group("series_id"))
            # 视频合集
            if regexp_collection.match(url):
                username, series_title = await asyncio.gather(
                    get_uploader_name(session, mid), get_collection_title(session, series_id)
                )
                Logger.custom(series_title, Badge("视频合集", fore="black", back="cyan"))

                acg_video_list = [
                    acg_video_item
                    for avid in await get_collection_avids(session, series_id)
                    for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
                ]
            # 视频列表
            else:
                username, series_title = await asyncio.gather(
                    get_uploader_name(session, mid), get_medialist_title(session, series_id)
                )
                Logger.custom(series_title, Badge("视频列表", fore="black", back="cyan"))

                acg_video_list = [
                    acg_video_item
                    for avid in await get_medialist_avids(session, series_id)
                    for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
                ]
            num_videos = len(acg_video_list)

            async def _parse_episodes_data_series(
                i: int,
                acg_video_item: AcgVideoListItem,
            ) -> Optional[tuple[int, EpisodeData]]:
                try:
                    _, title, pubdate = await asyncio.gather(
                        Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                        get_acg_video_title(session, acg_video_item["avid"]),
                        get_acg_video_pubdate(session, acg_video_item["avid"]),
                    )
                    return (
                        i,
                        await fetch_acg_video_data(
                            session,
                            acg_video_item["avid"],
                            i + 1,
                            acg_video_item,
                            args,
                            {
                                "series_title": series_title,
                                "username": username,  # 虽然默认模板的用不上，但这里可以提供一下
                                "title": title,
                                "pubdate": pubdate,
                            },
                            "{series_title}/{title}/{name}",
                        ),
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    return None

            coroutine_list = [
                _parse_episodes_data_series(i, acg_video_item) for i, acg_video_item in enumerate(acg_video_list)
            ]

        # 匹配为 UP 主个人空间
        elif match_obj := regexp_space_all.match(url):
            mid = MId(match_obj.group("mid"))
            username = await get_uploader_name(session, mid)
            Logger.custom(username, Badge("UP 主投稿视频", fore="black", back="cyan"))

            acg_video_list = [
                acg_video_item
                for avid in await get_uploader_space_all_videos_avids(session, mid)
                for acg_video_item in await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
            ]
            num_videos = len(acg_video_list)

            async def _parse_episodes_data_space(
                i: int,
                acg_video_item: AcgVideoListItem,
            ) -> Optional[tuple[int, EpisodeData]]:
                try:
                    _, title, pubdate = await asyncio.gather(
                        Fetcher.touch_url(session, acg_video_item["avid"].to_url()),
                        get_acg_video_title(session, acg_video_item["avid"]),
                        get_acg_video_pubdate(session, acg_video_item["avid"]),
                    )
                    return (
                        i,
                        await fetch_acg_video_data(
                            session,
                            acg_video_item["avid"],
                            i + 1,
                            acg_video_item,
                            args,
                            {"title": title, "username": username, "pubdate": pubdate},
                            "{username}的全部投稿视频/{title}/{name}",
                        ),
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    return None

            coroutine_list = [
                _parse_episodes_data_space(i, acg_video_item) for i, acg_video_item in enumerate(acg_video_list)
            ]

        else:
            # TODO: 指向文档中受支持的列表部分
            Logger.error("url 不正确呦～")
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)

        # 先解析各种资源链接
        for i, coro in enumerate(asyncio.as_completed(coroutine_list)):
            Logger.status.set(f"正在努力解析第 {i+1}/{num_videos} 个视频")
            results = await coro
            if results is not None:
                download_list.append(results)

        # 由于 asyncio.as_completed 的顺序是按照完成顺序的，所以需要重新排序下
        download_list.sort(key=lambda x: x[0])

        # 然后就可以下载啦～
        for i, (_, episode_data) in enumerate(download_list):
            Logger.custom(
                f"{episode_data['filename']}", Badge(f"[{i+1}/{len(download_list)}]", fore="black", back="cyan")
            )
            await process_video_download(
                session,
                episode_data,
                {
                    "require_video": args.require_video,
                    "video_quality": args.video_quality,
                    "video_download_codec": args.vcodec.split(":")[0],
                    "video_save_codec": args.vcodec.split(":")[1],
                    "require_audio": args.require_audio,
                    "audio_quality": args.audio_quality,
                    "audio_download_codec": args.acodec.split(":")[0],
                    "audio_save_codec": args.acodec.split(":")[1],
                    "overwrite": args.overwrite,
                    "block_size": int(args.block_size * 1024 * 1024),
                    "num_workers": args.num_workers,
                },
            )
            Logger.new_line()
