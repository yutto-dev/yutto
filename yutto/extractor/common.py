import argparse
import os
import sys
from typing import Optional

import aiohttp

from yutto.api.acg_video import AcgVideoListItem, get_acg_video_list, get_acg_video_playurl, get_acg_video_subtitles
from yutto.api.bangumi import (
    BangumiListItem,
    get_bangumi_list,
    get_bangumi_playurl,
    get_bangumi_subtitles,
    get_season_id_by_episode_id,
)
from yutto.api.danmaku import get_danmaku
from yutto.exceptions import ErrorCode
from yutto.processor.path_resolver import UNKNOWN, PathTemplateVariableDict, resolve_path_template
from yutto._typing import AvId, EpisodeData, EpisodeId
from yutto.utils.console.logger import Logger
from yutto.utils.danmaku import EmptyDanmakuData


async def extract_bangumi_data(
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
        bangumi_list = await get_bangumi_list(session, season_id, with_metadata=args.with_metadata)
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
    metadata = bangumi_info["metadata"]
    subpath_variables_base: PathTemplateVariableDict = {
        "id": id,
        "name": name,
        "title": UNKNOWN,
        "username": UNKNOWN,
        "series_title": UNKNOWN,
        "pubdate": UNKNOWN,
    }
    subpath_variables_base.update(subpath_variables)
    subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
    output_dir, filename = os.path.split(os.path.join(args.dir, subpath))
    return EpisodeData(
        videos=videos,
        audios=audios,
        subtitles=subtitles,
        danmaku=danmaku,
        metadata=metadata,
        output_dir=output_dir,
        tmp_dir=args.tmp_dir or output_dir,
        filename=filename,
    )


async def extract_acg_video_data(
    session: aiohttp.ClientSession,
    avid: AvId,
    page: int,
    acg_video_info: Optional[AcgVideoListItem],
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
) -> EpisodeData:
    acg_video_list = await get_acg_video_list(session, avid, with_metadata=args.with_metadata)
    if acg_video_info is None:
        acg_video_info = acg_video_list[page - 1]
    cid = acg_video_info["cid"]
    name = acg_video_info["name"]
    id = acg_video_info["id"]
    videos, audios = await get_acg_video_playurl(session, avid, cid)
    subtitles = await get_acg_video_subtitles(session, avid, cid) if not args.no_subtitle else []
    danmaku = await get_danmaku(session, cid, args.danmaku_format) if not args.no_danmaku else EmptyDanmakuData
    metadata = acg_video_info["metadata"]
    subpath_variables_base: PathTemplateVariableDict = {
        "id": id,
        "name": name,
        "title": UNKNOWN,
        "username": UNKNOWN,
        "series_title": UNKNOWN,
        "pubdate": UNKNOWN,
    }
    subpath_variables_base.update(subpath_variables)
    subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
    output_dir, filename = os.path.split(os.path.join(args.dir, subpath))
    return EpisodeData(
        videos=videos,
        audios=audios,
        subtitles=subtitles,
        danmaku=danmaku,
        metadata=metadata,
        output_dir=output_dir,
        tmp_dir=args.tmp_dir or output_dir,
        filename=filename,
    )
