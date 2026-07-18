from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from yutto.api.bangumi import (
    get_bangumi_playurl,
    get_bangumi_subtitles,
)
from yutto.api.cheese import get_cheese_playurl, get_cheese_subtitles
from yutto.api.danmaku import get_danmaku
from yutto.api.ugc_video import (
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
from yutto.path_templates import (
    UNKNOWN,
    resolve_path_template,
)
from yutto.types import EpisodeData, EpisodeInfo, ResolvableEpisode, format_ids
from yutto.utils.asynclib import CoroutineWrapper
from yutto.utils.console.logger import Logger
from yutto.utils.danmaku import EmptyDanmakuData
from yutto.utils.fetcher import Fetcher
from yutto.utils.metadata import MetaData, attach_chapter_info

if TYPE_CHECKING:
    import httpx

    from yutto.api.bangumi import (
        BangumiListItem,
    )
    from yutto.api.cheese import CheeseListItem
    from yutto.api.ugc_video import (
        UgcVideoListItem,
    )
    from yutto.path_templates import (
        PathTemplateVariableDict,
    )
    from yutto.types import AvId, EpisodeId, ExtractorOptions
    from yutto.utils.fetcher import FetcherContext


def _display_fields_from_metadata(metadata: MetaData | None) -> tuple[str, str, list[str]]:
    """listing 元数据中用于前端展示的字段：UP 主、简介、标签。"""
    if metadata is None:
        return "", "", []
    actors = metadata.get("actor") or []
    uploader = actors[0]["name"] if actors else ""
    return uploader, metadata.get("plot", ""), list(metadata.get("tag") or [])


def build_bangumi_info(
    bangumi_info: BangumiListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> EpisodeInfo:
    avid = bangumi_info["avid"]
    subpath_variables_base: PathTemplateVariableDict = {
        "id": bangumi_info["id"],
        "aid": str(avid.as_aid()),
        "bvid": str(avid.as_bvid()),
        "name": bangumi_info["name"],
        "title": UNKNOWN,
        "username": UNKNOWN,
        "series_title": UNKNOWN,
        "pubdate": UNKNOWN,
        "download_date": bangumi_info["metadata"]["dateadded"],
        "owner_uid": UNKNOWN,
        "owner_uname": UNKNOWN,
    }
    subpath_variables_base.update(subpath_variables)
    path = resolve_path_template(options["subpath_template"], auto_subpath_template, subpath_variables_base)
    uploader, description, tags = _display_fields_from_metadata(bangumi_info["metadata"])
    return EpisodeInfo(
        avid=avid,
        cid=bangumi_info["cid"],
        url=f"https://www.bilibili.com/bangumi/play/ep{bangumi_info['episode_id']}",
        name=bangumi_info["name"],
        title=str(subpath_variables_base["title"]),
        cover_url=bangumi_info["metadata"]["thumb"],
        uploader=uploader,
        description=description,
        tags=tags,
        path=Path(path),
        display_group=None,
    )


async def extract_bangumi_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    info: EpisodeInfo,
    bangumi_info: BangumiListItem,
    options: ExtractorOptions,
) -> EpisodeData | None:
    try:
        avid = info["avid"]
        cid = info["cid"]
        if bangumi_info["is_preview"]:
            Logger.warning(f"视频（{format_ids(avid, cid)}）是预览视频（疑似未登录或非大会员用户）")
        videos, audios = (
            await get_bangumi_playurl(ctx, client, avid, cid)
            if options["require_video"] or options["require_audio"]
            else ([], [])
        )
        subtitles = await get_bangumi_subtitles(ctx, client, avid, cid) if options["require_subtitle"] else []
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, options["danmaku_format"])
            if options["require_danmaku"]
            else EmptyDanmakuData
        )
        metadata = bangumi_info["metadata"] if options["require_metadata"] else None
        cover_data = (
            (await Fetcher.fetch_bin(ctx, client, info["cover_url"])).value_or(None)
            if options["require_cover"]
            else None
        )
        return EpisodeData(
            info=info,
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=[],
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


def make_bangumi_episode(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    bangumi_info: BangumiListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> ResolvableEpisode:
    info = build_bangumi_info(bangumi_info, options, subpath_variables, auto_subpath_template)
    return ResolvableEpisode(
        info=info,
        data_coro=CoroutineWrapper(extract_bangumi_data(ctx, client, info, bangumi_info, options)),
    )


def build_cheese_info(
    cheese_info: CheeseListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> EpisodeInfo:
    avid = cheese_info["avid"]
    subpath_variables_base: PathTemplateVariableDict = {
        "id": cheese_info["id"],
        "aid": str(avid.as_aid()),
        "bvid": str(avid.as_bvid()),
        "name": cheese_info["name"],
        "title": UNKNOWN,
        "username": UNKNOWN,
        "series_title": UNKNOWN,
        "pubdate": UNKNOWN,
        "download_date": UNKNOWN,
        "owner_uid": UNKNOWN,
        "owner_uname": UNKNOWN,
    }
    subpath_variables_base.update(subpath_variables)
    path = resolve_path_template(options["subpath_template"], auto_subpath_template, subpath_variables_base)
    uploader, description, tags = _display_fields_from_metadata(cheese_info["metadata"])
    return EpisodeInfo(
        avid=avid,
        cid=cheese_info["cid"],
        url=f"https://www.bilibili.com/cheese/play/ep{cheese_info['episode_id']}",
        name=cheese_info["name"],
        title=str(subpath_variables_base["title"]),
        cover_url=cheese_info["metadata"]["thumb"],
        uploader=uploader,
        description=description,
        tags=tags,
        path=Path(path),
        display_group=None,
    )


async def extract_cheese_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    episode_id: EpisodeId,
    info: EpisodeInfo,
    cheese_info: CheeseListItem,
    options: ExtractorOptions,
) -> EpisodeData | None:
    try:
        avid = info["avid"]
        cid = info["cid"]
        videos, audios = (
            await get_cheese_playurl(ctx, client, avid, episode_id, cid)
            if options["require_video"] or options["require_audio"]
            else ([], [])
        )
        subtitles = await get_cheese_subtitles(ctx, client, avid, cid) if options["require_subtitle"] else []
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, options["danmaku_format"])
            if options["require_danmaku"]
            else EmptyDanmakuData
        )
        metadata = cheese_info["metadata"] if options["require_metadata"] else None
        cover_data = (
            (await Fetcher.fetch_bin(ctx, client, info["cover_url"])).value_or(None)
            if options["require_cover"]
            else None
        )
        return EpisodeData(
            info=info,
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=[],
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


def make_cheese_episode(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    episode_id: EpisodeId,
    cheese_info: CheeseListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{name}",
) -> ResolvableEpisode:
    info = build_cheese_info(cheese_info, options, subpath_variables, auto_subpath_template)
    return ResolvableEpisode(
        info=info,
        data_coro=CoroutineWrapper(extract_cheese_data(ctx, client, episode_id, info, cheese_info, options)),
    )


def build_ugc_video_info(
    avid: AvId,
    ugc_video_info: UgcVideoListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
    display_group: str | None = None,
) -> EpisodeInfo:
    owner_uid: str = (
        ugc_video_info["metadata"]["actor"][0]["profile"].split("/")[-1]
        if ugc_video_info["metadata"]["actor"]
        else UNKNOWN
    )
    owner_uname: str = (
        ugc_video_info["metadata"]["actor"][0]["name"] if ugc_video_info["metadata"]["actor"] else UNKNOWN
    )
    subpath_variables_base: PathTemplateVariableDict = {
        "id": ugc_video_info["id"],
        "aid": str(avid.as_aid()),
        "bvid": str(avid.as_bvid()),
        "name": ugc_video_info["name"],
        "title": UNKNOWN,
        "username": owner_uname,  # 在不同情境下 username 的指代不明确，暂时约定 username 为视频作者名称，后续计划移除该字段
        "series_title": UNKNOWN,
        "pubdate": UNKNOWN,
        "download_date": ugc_video_info["metadata"]["dateadded"],
        "owner_uid": owner_uid,
        "owner_uname": owner_uname,
    }
    subpath_variables_base.update(subpath_variables)
    path = resolve_path_template(options["subpath_template"], auto_subpath_template, subpath_variables_base)
    uploader, description, tags = _display_fields_from_metadata(ugc_video_info["metadata"])
    return EpisodeInfo(
        avid=avid,
        cid=ugc_video_info["cid"],
        url=f"{avid.to_url()}?p={ugc_video_info['id']}",
        name=ugc_video_info["name"],
        title=str(subpath_variables_base["title"]),
        cover_url=ugc_video_info["metadata"]["thumb"],
        uploader=uploader,
        description=description,
        tags=tags,
        path=Path(path),
        display_group=display_group,
    )


async def extract_ugc_video_data(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    info: EpisodeInfo,
    ugc_video_info: UgcVideoListItem,
    options: ExtractorOptions,
) -> EpisodeData | None:
    try:
        avid = info["avid"]
        cid = info["cid"]
        videos, audios = (
            await get_ugc_video_playurl(ctx, client, avid, cid, options["ai_translation_language"])
            if options["require_video"] or options["require_audio"]
            else ([], [])
        )
        subtitles = await get_ugc_video_subtitles(ctx, client, avid, cid) if options["require_subtitle"] else []
        chapter_info_data = (
            await get_ugc_video_chapters(ctx, client, avid, cid) if options["require_chapter_info"] else []
        )
        danmaku = (
            await get_danmaku(ctx, client, cid, avid, options["danmaku_format"])
            if options["require_danmaku"]
            else EmptyDanmakuData
        )
        metadata = ugc_video_info["metadata"] if options["require_metadata"] else None
        if metadata and chapter_info_data:
            attach_chapter_info(metadata, chapter_info_data)
        cover_data = (
            (await Fetcher.fetch_bin(ctx, client, info["cover_url"])).value_or(None)
            if options["require_cover"]
            else None
        )
        return EpisodeData(
            info=info,
            videos=videos,
            audios=audios,
            subtitles=subtitles,
            metadata=metadata,
            danmaku=danmaku,
            cover_data=cover_data,
            chapter_info_data=chapter_info_data,
        )
    except (NoAccessPermissionError, HttpStatusError, UnSupportedTypeError, NotFoundError) as e:
        Logger.error(e.message)
        return None


def make_ugc_video_episode(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    avid: AvId,
    ugc_video_info: UgcVideoListItem,
    options: ExtractorOptions,
    subpath_variables: PathTemplateVariableDict,
    auto_subpath_template: str = "{title}",
    display_group: str | None = None,
) -> ResolvableEpisode:
    info = build_ugc_video_info(avid, ugc_video_info, options, subpath_variables, auto_subpath_template, display_group)
    return ResolvableEpisode(
        info=info,
        data_coro=CoroutineWrapper(extract_ugc_video_data(ctx, client, info, ugc_video_info, options)),
    )
