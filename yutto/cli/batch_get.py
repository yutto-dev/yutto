import argparse
import sys

import aiohttp

from yutto.api.acg_video import get_acg_video_list, get_acg_video_pubdate, get_acg_video_title
from yutto.api.bangumi import (
    get_bangumi_list,
    get_bangumi_title,
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.api.space import (
    get_all_favourites,
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
    regexp_favourite,
    regexp_favourite_all,
    regexp_medialist,
    regexp_series,
    regexp_space_all,
)
from yutto.typing import AId, BvId, EpisodeData, EpisodeId, FId, MediaId, MId, SeasonId, SeriesId
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.functiontools import sync


@sync
async def run(args: argparse.Namespace):
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        url: str = args.url
        url = await Fetcher.get_redirected_url(session, url)
        download_list: list[EpisodeData] = []

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
            title = await get_bangumi_title(session, season_id)
            Logger.custom(title, Badge("番剧", fore="black", back="cyan"))
            bangumi_list = await get_bangumi_list(session, season_id)
            # 如果没有 with_section 则不需要专区内容
            bangumi_list = list(filter(lambda item: args.with_section or not item["is_section"], bangumi_list))
            # 选集过滤
            episodes = parse_episodes(args.episodes, len(bangumi_list))
            bangumi_list = list(filter(lambda item: item["id"] in episodes, bangumi_list))
            for i, bangumi_item in enumerate(bangumi_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(bangumi_list)))
                try:
                    episode_data = await fetch_bangumi_data(
                        session, bangumi_item["episode_id"], bangumi_item, args, {"title": title}, "{title}/{name}"
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        # 匹配为投稿视频
        elif (match_obj := regexp_acg_video_av.match(url)) or (match_obj := regexp_acg_video_bv.match(url)):
            if "aid" in match_obj.groupdict().keys():
                avid = AId(match_obj.group("aid"))
            else:
                avid = BvId(match_obj.group("bvid"))
            title = await get_acg_video_title(session, avid)
            pubdate = await get_acg_video_pubdate(session, avid)
            Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))
            acg_video_list = await get_acg_video_list(session, avid)
            # 选集过滤
            episodes = parse_episodes(args.episodes, len(acg_video_list))
            acg_video_list = list(filter(lambda item: item["id"] in episodes, acg_video_list))
            for i, acg_video_item in enumerate(acg_video_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)))
                try:
                    episode_data = await fetch_acg_video_data(
                        session,
                        avid,
                        i + 1,
                        acg_video_item,
                        args,
                        {"title": title, "pubdate": pubdate},
                        "{title}/{name}",
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        # 匹配为收藏
        elif match_obj := regexp_favourite.match(url):
            mid = MId(match_obj.group("mid"))
            fid = FId(match_obj.group("fid"))
            username = await get_uploader_name(session, mid)
            favourite_info = await get_favourite_info(session, fid)
            Logger.custom(favourite_info["title"], Badge("收藏夹", fore="black", back="cyan"))

            acg_video_list = [
                acg_video_item
                for avid in await get_favourite_avids(session, fid)
                for acg_video_item in await get_acg_video_list(session, avid)
            ]
            for i, acg_video_item in enumerate(acg_video_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)))
                try:
                    # 在使用 SESSDATA 时，如果不去事先 touch 一下视频链接的话，是无法获取 episode_data 的
                    await Fetcher.touch_url(session, acg_video_item["avid"].to_url())
                    title = await get_acg_video_title(session, acg_video_item["avid"])
                    pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
                    episode_data = await fetch_acg_video_data(
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
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        # 匹配为用户全部收藏
        elif match_obj := regexp_favourite_all.match(url):
            mid = MId(match_obj.group("mid"))
            username = await get_uploader_name(session, mid)
            Logger.custom(username, Badge("用户收藏夹", fore="black", back="cyan"))

            acg_video_list = [
                (acg_video_item, fav["title"])
                for fav in await get_all_favourites(session, mid)
                for avid in await get_favourite_avids(session, fav["fid"])
                for acg_video_item in await get_acg_video_list(session, avid)
            ]

            for i, (acg_video_item, series_title) in enumerate(acg_video_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)))
                pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
                try:
                    await Fetcher.touch_url(session, acg_video_item["avid"].to_url())
                    title = await get_acg_video_title(session, acg_video_item["avid"])
                    episode_data = await fetch_acg_video_data(
                        session,
                        acg_video_item["avid"],
                        i + 1,
                        acg_video_item,
                        args,
                        {"title": title, "username": username, "series_title": series_title, "pubdate": pubdate},
                        "{username}的收藏夹/{series_title}/{title}/{name}",
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        # 匹配为视频合集
        elif (match_obj := regexp_medialist.match(url)) or (match_obj := regexp_series.match(url)):
            mid = MId(match_obj.group("mid"))
            series_id = SeriesId(match_obj.group("series_id"))
            username = await get_uploader_name(session, mid)
            series_title = await get_medialist_title(session, series_id)
            Logger.custom(series_title, Badge("视频合集", fore="black", back="cyan"))

            acg_video_list = [
                acg_video_item
                for avid in await get_medialist_avids(session, series_id)
                for acg_video_item in await get_acg_video_list(session, avid)
            ]
            for i, acg_video_item in enumerate(acg_video_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)))
                try:
                    await Fetcher.touch_url(session, acg_video_item["avid"].to_url())
                    title = await get_acg_video_title(session, acg_video_item["avid"])
                    pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
                    episode_data = await fetch_acg_video_data(
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
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        # 匹配为 UP 主个人空间
        elif match_obj := regexp_space_all.match(url):
            mid = MId(match_obj.group("mid"))
            username = await get_uploader_name(session, mid)
            Logger.custom(username, Badge("UP 主投稿视频", fore="black", back="cyan"))

            acg_video_list = [
                acg_video_item
                for avid in await get_uploader_space_all_videos_avids(session, mid)
                for acg_video_item in await get_acg_video_list(session, avid)
            ]

            for i, acg_video_item in enumerate(acg_video_list):
                Logger.status.set("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)))
                try:
                    await Fetcher.touch_url(session, acg_video_item["avid"].to_url())
                    title = await get_acg_video_title(session, acg_video_item["avid"])
                    pubdate = await get_acg_video_pubdate(session, acg_video_item["avid"])
                    episode_data = await fetch_acg_video_data(
                        session,
                        acg_video_item["avid"],
                        i + 1,
                        acg_video_item,
                        args,
                        {"title": title, "username": username, "pubdate": pubdate},
                        "{username}的全部投稿视频/{title}/{name}",
                    )
                except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
                    Logger.error(e.message)
                    continue
                download_list.append(episode_data)

        else:
            Logger.error("url 不正确～")
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)

        for i, episode_data in enumerate(download_list):
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
            Logger.print("")
