import argparse
import os
from typing import Optional

import aiohttp

from yutto._typing import AvId, EpisodeData, EpisodeId
from yutto.api.acg_video import AcgVideoListItem, get_acg_video_playurl, get_acg_video_subtitles
from yutto.api.bangumi import BangumiListItem, get_bangumi_playurl, get_bangumi_subtitles
from yutto.api.danmaku import get_danmaku
from yutto.exceptions import HttpStatusError, NoAccessPermissionError, NotFoundError, UnSupportedTypeError
from yutto.processor.path_resolver import UNKNOWN, PathTemplateVariableDict, resolve_path_template
from yutto.utils.console.logger import Logger
from yutto.utils.danmaku import EmptyDanmakuData


async def extract_bangumi_data(
    session: aiohttp.ClientSession,
    episode_id: EpisodeId,
    bangumi_info: BangumiListItem,
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> Optional[EpisodeData]:
    try:
        avid = bangumi_info["avid"]
        cid = bangumi_info["cid"]
        name = bangumi_info["name"]
        id = bangumi_info["id"]
        videos, audios = await get_bangumi_playurl(session, avid, episode_id, cid)
        subtitles = await get_bangumi_subtitles(session, avid, cid) if not args.no_subtitle else []
        danmaku = await get_danmaku(session, cid, args.danmaku_format) if not args.no_danmaku else EmptyDanmakuData
        metadata = bangumi_info["metadata"] if args.with_metadata else None
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
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


async def extract_acg_video_data(
    session: aiohttp.ClientSession,
    avid: AvId,
    acg_video_info: AcgVideoListItem,
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
) -> Optional[EpisodeData]:
    try:
        cid = acg_video_info["cid"]
        name = acg_video_info["name"]
        id = acg_video_info["id"]
        videos, audios = await get_acg_video_playurl(session, avid, cid)
        subtitles = await get_acg_video_subtitles(session, avid, cid) if not args.no_subtitle else []
        danmaku = await get_danmaku(session, cid, args.danmaku_format) if not args.no_danmaku else EmptyDanmakuData
        metadata = acg_video_info["metadata"] if args.with_metadata else None
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
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None
