from typing import TypedDict

from aiohttp import ClientSession

from yutto.api.types import AId, AvId, BvId, CId, EpisodeId
from yutto.processor.urlparser import regexp_bangumi_ep
from yutto.utils.fetcher import Fetcher


class VideoInfo(TypedDict):
    avid: AvId
    aid: AId
    bvid: BvId
    episode_id: EpisodeId
    is_bangumi: bool
    cid: CId
    picture: str
    title: str


async def get_video_info(session: ClientSession, avid: AvId) -> VideoInfo:
    info_api = "http://api.bilibili.com/x/web-interface/view?aid={aid}&bvid={bvid}"
    res_json = await Fetcher.fetch_json(session, info_api.format(**avid.to_dict()))
    res_json_data = res_json.get("data")
    assert res_json_data is not None, "响应数据无 data 域"
    episode_id = EpisodeId("")
    if res_json_data.get("redirect_url") and (ep_match := regexp_bangumi_ep.match(res_json_data["redirect_url"])):
        episode_id = EpisodeId(ep_match.group("episode_id"))
    return {
        "avid": BvId(res_json_data["bvid"]),
        "aid": AId(str(res_json_data["aid"])),
        "bvid": BvId(res_json_data["bvid"]),
        "episode_id": episode_id,
        "is_bangumi": bool(episode_id),
        "cid": CId(str(res_json_data["cid"])),
        "picture": res_json_data["pic"],
        "title": res_json_data["title"],
    }


async def is_vip(session: ClientSession) -> bool:
    info_api = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(session, info_api)
    res_json_data = res_json.get("data")
    if res_json_data.get("vipStatus") == 1:
        return True
    return False
