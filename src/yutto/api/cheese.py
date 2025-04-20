from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from yutto._typing import (
    AId,
    AudioUrlMeta,
    AvId,
    CId,
    EpisodeId,
    MultiLangSubtitle,
    SeasonId,
    VideoUrlMeta,
    format_ids,
)
from yutto.bilibili_typing.codec import audio_codec_map, video_codec_map
from yutto.exceptions import NoAccessPermissionError, UnSupportedTypeError
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.funcutils import data_has_chained_keys
from yutto.utils.metadata import MetaData
from yutto.utils.time import get_time_stamp_by_now

if TYPE_CHECKING:
    from httpx import AsyncClient


class CheeseListItem(TypedDict):
    url: str  # https://www.bilibili.com/cheese/play/ep487830
    id: int
    name: str
    cid: CId
    episode_id: EpisodeId
    avid: AvId
    metadata: MetaData


class CheeseList(TypedDict):
    title: str
    pages: list[CheeseListItem]


async def get_season_id_by_episode_id(ctx: FetcherContext, client: AsyncClient, episode_id: EpisodeId) -> SeasonId:
    home_url = f"https://api.bilibili.com/pugv/view/web/season?ep_id={episode_id}"
    res_json = await Fetcher.fetch_json(ctx, client, home_url)
    assert res_json is not None
    return SeasonId(str(res_json["data"]["season_id"]))


async def get_cheese_list(ctx: FetcherContext, client: AsyncClient, season_id: SeasonId) -> CheeseList:
    list_api = "https://api.bilibili.com/pugv/view/web/season?season_id={season_id}"
    resp_json = await Fetcher.fetch_json(ctx, client, list_api.format(season_id=season_id))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法解析该课程列表（season_id: {season_id}）")
    if resp_json.get("data") is None:
        raise NoAccessPermissionError(f"无法解析该课程列表（season_id: {season_id}），原因：{resp_json.get('message')}")
    result = resp_json["data"]
    section_episodes = result["episodes"]
    return {
        "title": result["title"],
        "pages": [
            {
                "id": i + 1,
                "name": item["title"],
                "cid": CId(str(item["cid"])),
                "episode_id": EpisodeId(str(item["id"])),
                "avid": AId(str(item["aid"])),
                "metadata": _parse_cheese_metadata(item),
                "url": f"https://www.bilibili.com/cheese/play/ep{item['id']}",
            }
            for i, item in enumerate(section_episodes)
        ],
    }


async def get_cheese_playurl(
    ctx: FetcherContext, client: AsyncClient, avid: AvId, episode_id: EpisodeId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = (
        "https://api.bilibili.com/pugv/player/web/playurl?avid={aid}&cid={"
        "cid}&qn=80&fnver=0&fnval=16&fourk=1&ep_id={episode_id}&from_client=BROWSER&drm_tech_type=2"
    )
    resp_json = await Fetcher.fetch_json(ctx, client, play_api.format(**avid.to_dict(), cid=cid, episode_id=episode_id))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（{format_ids(avid, cid)}）")
    if resp_json.get("data") is None:
        raise NoAccessPermissionError(
            f"无法获取该视频链接（{format_ids(avid, cid)}），原因：{resp_json.get('message')}"
        )
    if resp_json["data"]["is_preview"] == 1:
        Logger.warning(f"视频（{format_ids(avid, cid)}）是预览视频（疑似未登录或非大会员用户）")
    if resp_json["data"].get("dash") is None:
        raise UnSupportedTypeError(f"该视频（{format_ids(avid, cid)}）尚不支持 DASH 格式")
    return (
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
        ],
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
        ],
    )


async def get_cheese_subtitles(
    ctx: FetcherContext, client: AsyncClient, avid: AvId, cid: CId
) -> list[MultiLangSubtitle]:
    subtitile_api = "https://api.bilibili.com/x/player/v2?cid={cid}&aid={aid}&bvid={bvid}"
    subtitile_url = subtitile_api.format(**avid.to_dict(), cid=cid)
    subtitles_json_info = await Fetcher.fetch_json(ctx, client, subtitile_url)
    if subtitles_json_info is None:
        return []
    if not data_has_chained_keys(subtitles_json_info, ["data", "subtitle", "subtitles"]):
        Logger.warning(f"无法获取该视频的字幕（{format_ids(avid, cid)}），原因：{subtitles_json_info.get('message')}")
        return []
    subtitles_info = subtitles_json_info["data"]["subtitle"]
    results: list[MultiLangSubtitle] = []
    for sub_info in subtitles_info["subtitles"]:
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


def _parse_cheese_metadata(item: dict[str, Any]) -> MetaData:
    return MetaData(
        title=item["title"],
        show_title=item["title"],  # 无此字段，用 title 代替
        plot=item["title"],  # 无此字段，用 title 代替
        thumb=item["cover"],
        premiered=item["release_date"],
        dateadded=get_time_stamp_by_now(),
        source="",  # TODO
        actor=[],  # TODO
        genre=[],  # TODO
        tag=[],  # TODO
        website="",  # TODO
        original_filename="",  # TODO
        chapter_info_data=[],  # There are no chapter info in cheese for now
    )
