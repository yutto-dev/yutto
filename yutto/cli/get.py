import argparse
import os
import sys

import aiohttp

from yutto.api.acg_video import get_acg_video_playurl, get_acg_video_title, get_acg_video_list
from yutto.api.bangumi import get_bangumi_list, get_bangumi_playurl, get_bangumi_title, get_season_id_by_episode_id
from yutto.api.types import AId, AvId, BvId, CId, EpisodeId, MediaId, SeasonId
from yutto.processor.crawler import gen_cookies, gen_headers
from yutto.processor.downloader import download_video
from yutto.processor.urlparser import (
    regexp_acg_video_av,
    regexp_acg_video_av_short,
    regexp_acg_video_bv,
    regexp_acg_video_bv_short,
    regexp_bangumi_ep,
    regexp_bangumi_ep_short,
)
from yutto.utils.console.formatter import repair_filename
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.functiontools.sync import sync


def add_get_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("url", help="视频主页 url")
    parser.set_defaults(action=run)


@sync
async def run(args: argparse.Namespace):
    async with aiohttp.ClientSession(
        headers=gen_headers(),
        cookies=gen_cookies(args.sessdata),
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        if (match_obj := regexp_bangumi_ep.match(args.url)) or (match_obj := regexp_bangumi_ep_short.match(args.url)):
            # 匹配为番剧
            episode_id = EpisodeId(match_obj.group("episode_id"))
            season_id = await get_season_id_by_episode_id(session, episode_id)
            title = await get_bangumi_title(session, season_id)
            Logger.custom(title, Badge("番剧", fore="black", back="cyan"))
            bangumi_list = await get_bangumi_list(session, season_id)
            for bangumi_item in bangumi_list:
                if bangumi_item["episode_id"] == episode_id:
                    avid = bangumi_item["avid"]
                    cid = bangumi_item["cid"]
                    filename = bangumi_item["name"]
                    break
            else:
                Logger.error("在列表中未找到该剧集")
                sys.exit(1)
            videos, audios = await get_bangumi_playurl(session, avid, episode_id, cid)
        elif (
            (match_obj := regexp_acg_video_av.match(args.url))
            or (match_obj := regexp_acg_video_av_short.match(args.url))
            or (match_obj := regexp_acg_video_bv.match(args.url))
            or (match_obj := regexp_acg_video_bv_short.match(args.url))
        ):
            # 匹配为投稿视频
            page: int = 1
            if "aid" in match_obj.groupdict().keys():
                avid = AId(match_obj.group("aid"))
            else:
                avid = BvId(match_obj.group("bvid"))
            if match_obj.group("page") is not None:
                page = int(match_obj.group("page"))
            title = await get_acg_video_title(session, avid)
            Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))
            acg_video_list = await get_acg_video_list(session, avid)
            cid = acg_video_list[page - 1]["cid"]
            filename = acg_video_list[page - 1]["name"]
            videos, audios = await get_acg_video_playurl(session, avid, cid)
        else:
            Logger.error("url 不正确～")
            sys.exit(1)
        await download_video(
            session,
            videos,
            audios,
            args.dir,
            repair_filename(filename),
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
