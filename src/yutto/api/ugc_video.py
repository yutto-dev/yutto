from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, TypedDict, cast

from yutto._typing import (
    AId,
    AudioUrlMeta,
    AvId,
    BvId,
    CId,
    EpisodeId,
    MultiLangSubtitle,
    VideoUrlMeta,
    format_ids,
)
from yutto.bilibili_typing.codec import audio_codec_map, video_codec_map
from yutto.exceptions import (
    NoAccessPermissionError,
    NotFoundError,
    UnSupportedTypeError,
)
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.funcutils.data_access import data_has_chained_keys
from yutto.utils.metadata import Actor, ChapterInfoData, MetaData
from yutto.utils.time import get_time_stamp_by_now

if TYPE_CHECKING:
    from httpx import AsyncClient


class _UgcVideoPageInfo(TypedDict):
    part: str
    first_frame: str | None  # 该属性已经废弃，可能会在未来彻底移除


class _UgcVideoInfo(TypedDict):
    avid: AvId
    aid: AId
    bvid: BvId
    episode_id: EpisodeId
    is_bangumi: bool
    cid: CId
    picture: str
    title: str
    pubdate: int
    description: str
    pages: list[_UgcVideoPageInfo]
    genre: list[str]
    actor: list[Actor]
    tag: list[str]


class UgcVideoListItem(TypedDict):
    url: str  # https://www.bilibili.com/video/BV1vZ4y1M7mQ?p=1
    id: int
    name: str
    avid: AvId
    cid: CId
    metadata: MetaData


class UgcVideoList(TypedDict):
    title: str
    pubdate: int
    avid: AvId
    pages: list[UgcVideoListItem]


async def get_ugc_video_tag(ctx: FetcherContext, client: AsyncClient, avid: AvId) -> list[str]:
    tags: list[str] = []
    tag_api = "http://api.bilibili.com/x/tag/archive/tags?aid={aid}&bvid={bvid}"
    res_json = await Fetcher.fetch_json(ctx, client, tag_api.format(**avid.to_dict()))
    if res_json is None or res_json["code"] != 0:
        raise NotFoundError(f"无法获取视频 {avid} 标签")
    for tag in res_json["data"]:
        tags.append(tag["tag_name"])
    return tags


async def get_ugc_video_info(ctx: FetcherContext, client: AsyncClient, avid: AvId) -> _UgcVideoInfo:
    regex_ep = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")
    info_api = "http://api.bilibili.com/x/web-interface/view?aid={aid}&bvid={bvid}"
    res_json = await Fetcher.fetch_json(ctx, client, info_api.format(**avid.to_dict()))
    if res_json is None:
        raise NotFoundError(f"无法获取该视频 {avid} 信息")
    res_json_data = res_json.get("data")
    if res_json["code"] == 62002:
        raise NotFoundError(f"无法下载该视频 {avid}，原因：{res_json['message']}")
    if res_json["code"] == 62012:
        raise NoAccessPermissionError(
            f"无法获取该视频 {avid} 信息，原因：{res_json['message']}（当前稿件up主设置为仅自见）"
        )
    if res_json["code"] == -404:
        raise NotFoundError(f"啊叻？视频 {avid} 不见了诶")
    assert res_json_data is not None, "响应数据无 data 域"
    if res_json_data.get("forward"):
        forward_avid = AId(str(res_json_data["forward"]))
        Logger.info(f"视频 {avid} 撞车了哦！正在跳转到原视频 {forward_avid}～")
        return await get_ugc_video_info(ctx, client, forward_avid)
    episode_id = EpisodeId("")
    if res_json_data.get("redirect_url") and (ep_match := regex_ep.match(res_json_data["redirect_url"])):
        episode_id = EpisodeId(ep_match.group("episode_id"))

    actors = _parse_actor_info(res_json_data)
    genres = _parse_genre_info(res_json_data)
    tags: list[str] = await get_ugc_video_tag(ctx, client, avid)
    return {
        "avid": BvId(res_json_data["bvid"]),
        "aid": AId(str(res_json_data["aid"])),
        "bvid": BvId(res_json_data["bvid"]),
        "episode_id": episode_id,
        "is_bangumi": bool(episode_id),
        "cid": CId(str(res_json_data["cid"])),
        "picture": res_json_data["pic"],
        "title": res_json_data["title"],
        "pubdate": res_json_data["pubdate"],
        "description": res_json_data["desc"],
        "pages": [
            {
                "part": page["part"],
                "first_frame": page.get("first_frame"),
            }
            for page in res_json_data["pages"]
        ],
        "actor": actors,
        "tag": tags,
        "genre": genres,
    }


async def get_ugc_video_list(ctx: FetcherContext, client: AsyncClient, avid: AvId) -> UgcVideoList:
    video_info = await get_ugc_video_info(ctx, client, avid)
    if avid not in [video_info["aid"], video_info["bvid"]]:
        avid = video_info["avid"]
    video_title = video_info["title"]
    result: UgcVideoList = {
        "title": video_title,
        "avid": avid,
        "pubdate": video_info["pubdate"],
        "pages": [],
    }
    list_api = "https://api.bilibili.com/x/player/pagelist?aid={aid}&bvid={bvid}&jsonp=jsonp"
    res_json = await Fetcher.fetch_json(ctx, client, list_api.format(**avid.to_dict()))
    if res_json is None or res_json.get("data") is None:
        Logger.warning(f"啊叻？视频 {avid} 不见了诶")
        return result

    # 对无意义的分 p 视频名进行修改
    for i, (item, page_info) in enumerate(zip(cast("list[Any]", res_json["data"]), video_info["pages"], strict=True)):
        # TODO: 这里 part 出现了两次，需要都修改，后续去除其中一个冗余数据
        if _is_meaningless_name(item["part"]):
            item["part"] = f"{video_title}_P{i + 1:02}"
        if _is_meaningless_name(page_info["part"]):
            page_info["part"] = f"{video_title}_P{i + 1:02}"

    result["pages"] = [
        {
            "id": i + 1,
            "name": item["part"],
            "avid": avid,
            "cid": CId(str(item["cid"])),
            "metadata": _parse_ugc_video_metadata(video_info, page_info, is_first_page=i == 0),
            "url": video_info["bvid"].to_url() + f"?p={i + 1}",
        }
        for i, (item, page_info) in enumerate(
            zip(cast("list[Any]", res_json["data"]), video_info["pages"], strict=True)
        )
    ]
    return result


async def get_ugc_video_playurl(
    ctx: FetcherContext, client: AsyncClient, avid: AvId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    # 4048 = 16(useDash) | 64(useHDR) | 128(use4K) | 256(useDolby) | 512(useXXX) | 1024(use8K) | 2048(useAV1)
    play_api = "https://api.bilibili.com/x/player/playurl?avid={aid}&bvid={bvid}&cid={cid}&qn=127&type=&otype=json&fnver=0&fnval=4048&fourk=1"

    resp_json = await Fetcher.fetch_json(ctx, client, play_api.format(**avid.to_dict(), cid=cid))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（{format_ids(avid, cid)}）")
    if resp_json.get("data") is None:
        raise NoAccessPermissionError(
            f"无法获取该视频链接（{format_ids(avid, cid)}），原因：{resp_json.get('message')}"
        )
    if resp_json["data"].get("dash") is None:
        raise UnSupportedTypeError(f"该视频（{format_ids(avid, cid)}）尚不支持 DASH 格式")
    videos: list[VideoUrlMeta] = (
        [
            {
                "url": video["base_url"],
                "mirrors": video["backup_url"] if video["backup_url"] is not None else [],
                "codec": video_codec_map[video["codecid"]],
                "width": video["width"],
                "height": video["height"],
                "quality": video["id"],
            }
            for video in resp_json["data"]["dash"]["video"]
        ]
        if resp_json["data"]["dash"]["video"]
        else []
    )
    audios: list[AudioUrlMeta] = (
        [
            {
                "url": audio["base_url"],
                "mirrors": audio["backup_url"] if audio["backup_url"] is not None else [],
                "codec": audio_codec_map[audio["codecid"]],
                "width": 0,
                "height": 0,
                "quality": audio["id"],
            }
            for audio in resp_json["data"]["dash"]["audio"]
        ]
        if resp_json["data"]["dash"]["audio"]
        else []
    )
    if resp_json["data"]["dash"]["dolby"] is not None and resp_json["data"]["dash"]["dolby"]["audio"] is not None:
        dolby_audios_json = resp_json["data"]["dash"]["dolby"]["audio"]
        audios.extend(
            {
                "url": dolby_audio_json["base_url"],
                "mirrors": dolby_audio_json["backup_url"] if dolby_audio_json["backup_url"] is not None else [],
                "codec": "eac3",  # TODO: 由于这里的 codecid 仍然是 0，所以无法通过 audio_codec_map 转换，暂时直接硬编码
                "width": 0,
                "height": 0,
                "quality": dolby_audio_json["id"],
            }
            for dolby_audio_json in dolby_audios_json
        )
    if resp_json["data"]["dash"]["flac"] is not None and resp_json["data"]["dash"]["flac"]["audio"] is not None:
        hi_res_audio_json = resp_json["data"]["dash"]["flac"]["audio"]
        audios.append(
            {
                "url": hi_res_audio_json["base_url"],
                "mirrors": hi_res_audio_json["backup_url"] if hi_res_audio_json["backup_url"] is not None else [],
                "codec": "flac",  # TODO: 同上，硬编码
                "width": 0,
                "height": 0,
                "quality": hi_res_audio_json["id"],
            }
        )

    return (videos, audios)


async def get_ugc_video_subtitles(
    ctx: FetcherContext, client: AsyncClient, avid: AvId, cid: CId
) -> list[MultiLangSubtitle]:
    subtitile_api = "https://api.bilibili.com/x/player/wbi/v2?aid={aid}&bvid={bvid}&cid={cid}"
    subtitile_url = subtitile_api.format(**avid.to_dict(), cid=cid)
    res_json = await Fetcher.fetch_json(ctx, client, subtitile_url)
    assert res_json is not None, "无法获取该视频的字幕信息"
    if not data_has_chained_keys(res_json, ["data", "subtitle", "subtitles"]):
        return []
    results: list[MultiLangSubtitle] = []
    for sub_info in res_json["data"]["subtitle"]["subtitles"]:
        subtitle_text = await Fetcher.fetch_json(ctx, client, "https:" + sub_info["subtitle_url"])
        if subtitle_text is None:
            continue
        results.append(
            {
                "lang": sub_info["lan_doc"],
                "lines": subtitle_text["body"],
            }
        )
    return results


async def get_ugc_video_chapters(
    ctx: FetcherContext, client: AsyncClient, avid: AvId, cid: CId
) -> list[ChapterInfoData]:
    chapter_api = "https://api.bilibili.com/x/player/v2?avid={aid}&bvid={bvid}&cid={cid}"
    chapter_url = chapter_api.format(**avid.to_dict(), cid=cid)
    chapter_json_info = await Fetcher.fetch_json(ctx, client, chapter_url)
    if chapter_json_info is None:
        return []
    if not data_has_chained_keys(chapter_json_info, ["data", "view_points"]):
        Logger.warning(f"无法获取该视频的章节信息（{format_ids(avid, cid)}），原因：{chapter_json_info.get('message')}")
        return []

    raw_chapter_info = chapter_json_info["data"]["view_points"]
    return [
        {"content": chapter_info["content"], "start": chapter_info["from"], "end": chapter_info["to"]}
        for chapter_info in raw_chapter_info
    ]


def _parse_ugc_video_metadata(
    video_info: _UgcVideoInfo,
    page_info: _UgcVideoPageInfo,
    is_first_page: bool = False,
) -> MetaData:
    return MetaData(
        title=page_info["part"],
        show_title=page_info["part"],
        plot=video_info["description"],
        thumb=video_info["picture"],
        premiered=video_info["pubdate"],
        dateadded=get_time_stamp_by_now(),
        actor=video_info["actor"],
        genre=video_info["genre"],
        tag=video_info["tag"],
        source="",  # TODO
        original_filename="",  # TODO
        website=video_info["bvid"].to_url(),
        chapter_info_data=[],
    )


def _parse_actor_info(video_info: dict[str, Any]):
    actors: list[Actor] = []
    if video_info.get("staff") and isinstance(video_info["staff"], list):
        _index: int = 0
        staff_list: list[dict[str, Any]] = video_info["staff"]
        for staff in staff_list:
            actors.append(
                Actor(
                    name=staff["name"],
                    role=staff["title"],
                    thumb=staff["face"],
                    profile=f"https://space.bilibili.com/{staff['mid']}",
                    order=_index,
                )
            )
            _index += 1
    elif video_info.get("owner") and isinstance(video_info["owner"], dict):
        staff_info: dict[str, Any] = video_info["owner"]
        actors.append(
            Actor(
                name=staff_info["name"],
                role="UP主",
                thumb=staff_info["face"],
                profile=f"https://space.bilibili.com/{staff_info['mid']}",
                order=0,
            )
        )
    else:
        Logger.warning("未找到演职人员信息")
    return actors


def _parse_genre_info(video_info: dict[str, Any]) -> list[str]:
    genres: list[str] = []
    if video_info.get("tname") and isinstance(video_info["tname"], str):
        genres.append(video_info["tname"])
    return genres


def _is_meaningless_name(name: str) -> bool:
    """检测名称是否为无意义的名称"""
    # name 为空
    if not name:
        return True

    # name 为视频文件名
    video_ext_list = [".mp4", ".flv", ".mkv", ".avi", ".wmv", ".mov", ".mpg", ".mpeg", ".ts"]
    for video_ext in video_ext_list:
        if name.endswith(video_ext):
            return True
    return False
