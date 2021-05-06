import argparse
import sys
from typing import Optional

import aiohttp

from yutto.api.acg_video import get_acg_video_list, get_acg_video_playurl, get_acg_video_subtitles, get_acg_video_title
from yutto.api.bangumi import (
    get_bangumi_list,
    get_bangumi_playurl,
    get_bangumi_subtitles,
    get_bangumi_title,
    get_season_id_by_episode_id,
    get_season_id_by_media_id,
)
from yutto.api.danmaku import get_xml_danmaku
from yutto.api.types import AId, AudioUrlMeta, BvId, EpisodeId, MediaId, MultiLangSubtitle, SeasonId, VideoUrlMeta
from yutto.cli import check_options
from yutto.processor.downloader import download_video
from yutto.processor.filter import parse_episodes
from yutto.processor.path_resolver import resolve_path, resolve_path_pattern
from yutto.processor.urlparser import (
    regexp_acg_video_av,
    regexp_acg_video_av_short,
    regexp_acg_video_bv,
    regexp_acg_video_bv_short,
    regexp_bangumi_ep,
    regexp_bangumi_ep_short,
    regexp_bangumi_md,
    regexp_bangumi_ss,
    regexp_bangumi_ss_short,
)
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import DanmakuData
from yutto.utils.fetcher import Fetcher
from yutto.utils.functiontools.sync import sync


def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("url", help="视频主页 url")
    parser.add_argument("-p", "--episodes", default="^~$", help="选集")
    parser.add_argument("-s", "--with-section", action="store_true", help="同时下载附加剧集（PV、预告以及特别篇等专区内容）")
    parser.set_defaults(action=run)


@sync
async def run(args: argparse.Namespace):
    check_options.check_batch_options(args)
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        download_list: list[
            tuple[list[VideoUrlMeta], list[AudioUrlMeta], str, str, list[MultiLangSubtitle], Optional[str]]
        ] = []
        if (
            (match_obj := regexp_bangumi_ep.match(args.url))
            or (match_obj := regexp_bangumi_ep_short.match(args.url))
            or (match_obj := regexp_bangumi_ss.match(args.url))
            or (match_obj := regexp_bangumi_ss_short.match(args.url))
            or (match_obj := regexp_bangumi_md.match(args.url))
        ):
            # 匹配为番剧
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
                Logger.info("正在努力解析第 {}/{} 个视频".format(i + 1, len(bangumi_list)), end="\r")
                avid = bangumi_item["avid"]
                cid = bangumi_item["cid"]
                episode_id = bangumi_item["episode_id"]
                name = bangumi_item["name"]
                id = bangumi_item["id"]
                videos, audios = await get_bangumi_playurl(session, avid, episode_id, cid)
                # fmt: off
                subpath = resolve_path_pattern(
                    args.path_pattern,
                    "{title}/{name}",
                    {
                        "title": title,
                        "id": id,
                        "name": name
                    })
                # fmt: on
                output_dir, filename = resolve_path(args.dir, subpath)
                subtitles = await get_bangumi_subtitles(session, avid, cid) if not args.no_subtitle else []
                xml_danmaku = await get_xml_danmaku(session, cid) if args.danmaku != "no" else None
                download_list.append((videos, audios, output_dir, filename, subtitles, xml_danmaku))
        elif (
            (match_obj := regexp_acg_video_av.match(args.url))
            or (match_obj := regexp_acg_video_av_short.match(args.url))
            or (match_obj := regexp_acg_video_bv.match(args.url))
            or (match_obj := regexp_acg_video_bv_short.match(args.url))
        ):
            # 匹配为投稿视频
            if "aid" in match_obj.groupdict().keys():
                avid = AId(match_obj.group("aid"))
            else:
                avid = BvId(match_obj.group("bvid"))
            title = await get_acg_video_title(session, avid)
            Logger.custom(title, Badge("投稿视频", fore="black", back="cyan"))
            acg_video_list = await get_acg_video_list(session, avid)
            # 选集过滤
            episodes = parse_episodes(args.episodes, len(acg_video_list))
            acg_video_list = list(filter(lambda item: item["id"] in episodes, acg_video_list))
            for i, acg_video_item in enumerate(acg_video_list):
                Logger.info("正在努力解析第 {}/{} 个视频".format(i + 1, len(acg_video_list)), end="\r")
                cid = acg_video_item["cid"]
                name = acg_video_item["name"]
                id = acg_video_item["id"]
                videos, audios = await get_acg_video_playurl(session, avid, cid)
                # fmt: off
                subpath = resolve_path_pattern(
                    args.path_pattern,
                    "{title}/{name}",
                    {
                        "title": title,
                        "id": id,
                        "name": name
                    })
                # fmt: on
                output_dir, filename = resolve_path(args.dir, subpath)
                subtitles = await get_acg_video_subtitles(session, avid, cid) if not args.no_subtitle else []
                xml_danmaku = await get_xml_danmaku(session, cid) if args.danmaku != "no" else None
                download_list.append((videos, audios, output_dir, filename, subtitles, xml_danmaku))
        else:
            Logger.error("url 不正确～")
            sys.exit(1)
        for videos, audios, output_dir, filename, subtitles, xml_danmaku in download_list:
            # fmt: off
            danmaku: DanmakuData = {
                "source_type": "xml",
                "save_type": args.danmaku,
                "data": xml_danmaku
            }
            # fmt: on

            await download_video(
                session,
                videos,
                audios,
                output_dir,
                filename,
                subtitles,
                danmaku,
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
