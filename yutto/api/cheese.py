from __future__ import annotations

from typing import TypedDict

from aiohttp import ClientSession

from yutto._typing import (
    AudioUrlMeta,
    AvId,
    BvId,
    CId,
    EpisodeId,
    MultiLangSubtitle,
    SeasonId,
    VideoUrlMeta,
)
from yutto.bilibili_typing.codec import audio_codec_map, video_codec_map
from yutto.exceptions import NoAccessPermissionError, UnSupportedTypeError
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher


class CheeseListItem(TypedDict):
    id: int
    name: str
    cid: CId
    episode_id: EpisodeId
    avid: AvId
    is_section: bool  # 是否属于专区


class CheeseList(TypedDict):
    title: str
    pages: list[CheeseListItem]


async def get_season_id_by_episode_id(session: ClientSession, episode_id: EpisodeId) -> SeasonId:
    home_url = f"https://api.bilibili.com/pugv/view/web/season?ep_id={episode_id}"
    res_json = await Fetcher.fetch_json(session, home_url)
    assert res_json is not None
    return SeasonId(str(res_json["data"]["season_id"]))


async def get_cheese_list(session: ClientSession, season_id: SeasonId) -> CheeseList:
    list_api = "https://api.bilibili.com/pugv/view/web/season?season_id={season_id}"
    resp_json = await Fetcher.fetch_json(session, list_api.format(season_id=season_id))
    assert resp_json is not None
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
                "avid": BvId(item["aid"]),
                "is_section": i >= len(section_episodes),
            }
            for i, item in enumerate(section_episodes)
        ],
    }


async def get_cheese_playurl(
    session: ClientSession, avid: AvId, episode_id: EpisodeId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = "https://api.bilibili.com/pugv/player/web/playurl?avid={aid}&cid={cid}&qn=80&fnver=0&fnval=16&fourk=1&ep_id={episode_id}&from_client=BROWSER&drm_tech_type=2"
    resp_json = await Fetcher.fetch_json(session, play_api.format(**avid.to_dict(), cid=cid, episode_id=episode_id))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}）")
    if resp_json.get("data") is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}），原因：{resp_json.get('message')}")
    if resp_json["data"]["is_preview"] == 1:
        Logger.warning(f"视频（avid: {avid}, cid: {cid}）是预览视频（疑似未登录或非大会员用户）")
    if resp_json["data"].get("dash") is None:
        raise UnSupportedTypeError(f"该视频（avid: {avid}, cid: {cid}）尚不支持 DASH 格式")
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
