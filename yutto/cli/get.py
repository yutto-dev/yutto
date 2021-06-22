import argparse
import os
import sys
from typing import Optional

import aiohttp

from yutto.api.acg_video import (
    AcgVideoListItem,
    get_acg_video_list,
    get_acg_video_playurl,
    get_acg_video_subtitles,
    get_acg_video_title,
)
from yutto.api.bangumi import (
    BangumiListItem,
    get_bangumi_list,
    get_bangumi_playurl,
    get_bangumi_subtitles,
    get_bangumi_title,
    get_season_id_by_episode_id,
)
from yutto.api.danmaku import get_danmaku
from yutto.exceptions import ErrorCode, HttpStatusError, NoAccessPermissionError, UnSupportedTypeError
from yutto.processor.downloader import process_video_download
from yutto.processor.path_resolver import PathTemplateVariableDict, resolve_path_template
from yutto.processor.urlparser import regexp_acg_video_av, regexp_acg_video_bv, regexp_bangumi_ep
from yutto.typing import AId, AvId, BvId, EpisodeData, EpisodeId
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import EmptyDanmakuData
from yutto.utils.fetcher import Fetcher
from yutto.utils.functiontools.sync import sync


async def fetch_bangumi_data(
    session: aiohttp.ClientSession,
    episode_id: EpisodeId,
    bangumi_info: Optional[BangumiListItem],
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> EpisodeData:
    season_id = await get_season_id_by_episode_id(session, episode_id)
    # 如果不包含详细信息，需从列表中解析
    if bangumi_info is None:
        bangumi_list = await get_bangumi_list(session, season_id)
        for bangumi_item in bangumi_list:
            if bangumi_item["episode_id"] == episode_id:
                bangumi_info = bangumi_item
                break
        else:
            Logger.error("在列表中未找到该剧集")
            sys.exit(ErrorCode.EPISODE_NOT_FOUND_ERROR.value)
    avid = bangumi_info["avid"]
    cid = bangumi_info["cid"]
    name = bangumi_info["name"]
    id = bangumi_info["id"]
    videos, audios = await get_bangumi_playurl(session, avid, episode_id, cid)
    subtitles = await get_bangumi_subtitles(session, avid, cid) if not args.no_subtitle else []
    danmaku = await get_danmaku(session, cid, args.danmaku_format) if not args.no_danmaku else EmptyDanmakuData
    # fmt: off
    subpath_variables_base: PathTemplateVariableDict = {
        "id": id,
        "name": name,
        "title": "",
        "username": "",
    }
    # fmt: on
    subpath_variables_base.update(subpath_variables)
    subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
    output_dir, filename = os.path.split(os.path.join(args.dir, subpath))
    # fmt: off
    return EpisodeData(
        videos = videos,
        audios = audios,
        subtitles = subtitles,
        danmaku = danmaku,
        output_dir = output_dir,
        filename = filename
    )
    # fmt: on


async def fetch_acg_video_data(
    session: aiohttp.ClientSession,
    avid: AvId,
    page: int,
    acg_video_info: Optional[AcgVideoListItem],
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
) -> EpisodeData:
    acg_video_list = await get_acg_video_list(session, avid)
    if acg_video_info is None:
        acg_video_info = acg_video_list[page - 1]
    cid = acg_video_info["cid"]
    name = acg_video_info["name"]
    id = acg_video_info["id"]
    videos, audios = await get_acg_video_playurl(session, avid, cid)
    subtitles = await get_acg_video_subtitles(session, avid, cid) if not args.no_subtitle else []
    danmaku = await get_danmaku(session, cid, args.danmaku_format) if not args.no_danmaku else EmptyDanmakuData
    # fmt: off
    subpath_variables_base: PathTemplateVariableDict = {
        "id": id,
        "name": name,
        "title": "",
        "username": "",
    }
    # fmt: on
    subpath_variables_base.update(subpath_variables)
    subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
    output_dir, filename = os.path.split(os.path.join(args.dir, subpath))
    # fmt: off
    return EpisodeData(
        videos = videos,
        audios = audios,
        subtitles = subtitles,
        danmaku = danmaku,
        output_dir = output_dir,
        filename = filename
    )
    # fmt: on


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
        if match_obj := regexp_bangumi_ep.match(url):
            # 匹配为番剧
            episode_id = EpisodeId(match_obj.group("episode_id"))
            season_id = await get_season_id_by_episode_id(session, episode_id)
            title = await get_bangumi_title(session, season_id)
            Logger.custom(title, Badge("番剧", fore="black", back="cyan"))
            try:
                episode_data = await fetch_bangumi_data(session, episode_id, None, args, {"title": title}, "{name}")
            except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
                Logger.error(e.message)
                sys.exit(e.code.value)

        elif (match_obj := regexp_acg_video_av.match(url)) or (match_obj := regexp_acg_video_bv.match(url)):
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
            try:
                episode_data = await fetch_acg_video_data(
                    session,
                    avid,
                    page,
                    None,
                    args,
                    {"title": title},
                    "{title}",
                )
            except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError) as e:
                Logger.error(e.message)
                sys.exit(e.code.value)

        else:
            Logger.error("url 不正确～")
            sys.exit(ErrorCode.WRONG_URL_ERROR.value)

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
