from __future__ import annotations

from typing import TYPE_CHECKING

from yutto._typing import AvId, EpisodeData, EpisodeId, format_ids
from yutto.api.bangumi import (
    BangumiListItem,
    get_bangumi_playurl,
    get_bangumi_subtitles,
)
from yutto.api.cheese import CheeseListItem, get_cheese_playurl, get_cheese_subtitles
from yutto.api.danmaku import get_danmaku
from yutto.api.ugc_video import (
    UgcVideoListItem,
    get_ugc_video_chapters,
    get_ugc_video_playurl,
    get_ugc_video_subtitles,
)
from yutto.exceptions import (
    HttpStatusError,
    NoAccessPermissionError,
    NotFoundError,
    UnSupportedTypeError,
)
from yutto.processor.path_resolver import (
    UNKNOWN,
    PathTemplateVariableDict,
    resolve_path_template,
)
from yutto.utils.console.logger import Logger
from yutto.utils.danmaku import EmptyDanmakuData
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.metadata import attach_chapter_info

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    import httpx


async def extract_bangumi_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    bangumi_info: BangumiListItem,
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> EpisodeData | None:
    try:
        avid = bangumi_info["avid"]
        cid = bangumi_info["cid"]
        name = bangumi_info["name"]
        id = bangumi_info["id"]
        if bangumi_info["is_preview"]:
            Logger.warning(f"视频（{format_ids(avid, cid)}）是预览视频（疑似未登录或非大会员用户）")
        videos, audios = (
            await get_bangumi_playurl(ctx, client, avid, cid) if args.require_video or args.require_audio else ([], [])
        )
        subtitles = await get_bangumi_subtitles(ctx, client, avid, cid) if args.require_subtitle else []
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, args.danmaku_format) if args.require_danmaku else EmptyDanmakuData
        )
        metadata = bangumi_info["metadata"] if args.require_metadata else None
        cover_data = (
            await Fetcher.fetch_bin(ctx, client, bangumi_info["metadata"]["thumb"]) if args.require_cover else None
        )
        subpath_variables_base: PathTemplateVariableDict = {
            "id": id,
            "name": name,
            "title": UNKNOWN,
            "username": UNKNOWN,
            "series_title": UNKNOWN,
            "pubdate": UNKNOWN,
            "download_date": bangumi_info["metadata"]["dateadded"],
            "owner_uid": UNKNOWN,
        }
        subpath_variables_base.update(subpath_variables)
        subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
        file_path: Path = args.dir / subpath
        output_dir, filename = file_path.parent, file_path.name
        return EpisodeData(
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=[],
            output_dir=output_dir,
            tmp_dir=args.tmp_dir or output_dir,
            filename=filename,
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


async def extract_cheese_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    episode_id: EpisodeId,
    cheese_info: CheeseListItem,
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> EpisodeData | None:
    try:
        avid = cheese_info["avid"]
        cid = cheese_info["cid"]
        name = cheese_info["name"]
        id = cheese_info["id"]
        videos, audios = (
            await get_cheese_playurl(ctx, client, avid, episode_id, cid)
            if args.require_video or args.require_audio
            else ([], [])
        )
        subtitles = await get_cheese_subtitles(ctx, client, avid, cid) if args.require_subtitle else []
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, args.danmaku_format) if args.require_danmaku else EmptyDanmakuData
        )
        metadata = cheese_info["metadata"] if args.require_metadata else None
        cover_data = (
            await Fetcher.fetch_bin(ctx, client, cheese_info["metadata"]["thumb"]) if args.require_cover else None
        )
        subpath_variables_base: PathTemplateVariableDict = {
            "id": id,
            "name": name,
            "title": UNKNOWN,
            "username": UNKNOWN,
            "series_title": UNKNOWN,
            "pubdate": UNKNOWN,
            "download_date": UNKNOWN,
            "owner_uid": UNKNOWN,
        }
        subpath_variables_base.update(subpath_variables)
        subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
        file_path: Path = args.dir / subpath
        output_dir, filename = file_path.parent, file_path.name
        return EpisodeData(
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=[],
            output_dir=output_dir,
            tmp_dir=args.tmp_dir or output_dir,
            filename=filename,
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


async def extract_ugc_video_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    avid: AvId,
    ugc_video_info: UgcVideoListItem,
    args: argparse.Namespace,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
) -> EpisodeData | None:
    try:
        cid = ugc_video_info["cid"]
        name = ugc_video_info["name"]
        id = ugc_video_info["id"]
        videos, audios = (
            await get_ugc_video_playurl(ctx, client, avid, cid)
            if args.require_video or args.require_audio
            else ([], [])
        )
        subtitles = await get_ugc_video_subtitles(ctx, client, avid, cid) if args.require_subtitle else []
        chapter_info_data = await get_ugc_video_chapters(ctx, client, avid, cid) if args.require_chapter_info else []
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, args.danmaku_format) if args.require_danmaku else EmptyDanmakuData
        )
        metadata = ugc_video_info["metadata"] if args.require_metadata else None
        if metadata and chapter_info_data:
            attach_chapter_info(metadata, chapter_info_data)
        cover_data = (
            await Fetcher.fetch_bin(ctx, client, ugc_video_info["metadata"]["thumb"]) if args.require_cover else None
        )
        owner_uid: str = (
            ugc_video_info["metadata"]["actor"][0]["profile"].split("/")[-1]
            if ugc_video_info["metadata"]["actor"]
            else UNKNOWN
        )
        subpath_variables_base: PathTemplateVariableDict = {
            "id": id,
            "name": name,
            "title": UNKNOWN,
            "username": UNKNOWN,
            "series_title": UNKNOWN,
            "pubdate": UNKNOWN,
            "download_date": ugc_video_info["metadata"]["dateadded"],
            "owner_uid": owner_uid,
        }
        subpath_variables_base.update(subpath_variables)
        subpath = resolve_path_template(args.subpath_template, auto_subpath_template, subpath_variables_base)
        file_path: Path = args.dir / subpath
        output_dir, filename = file_path.parent, file_path.name
        return EpisodeData(
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=chapter_info_data,
            output_dir=output_dir,
            tmp_dir=args.tmp_dir or output_dir,
            filename=filename,
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None
