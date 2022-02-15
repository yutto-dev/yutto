import re
from typing import Optional, TypedDict

from aiohttp import ClientSession

from yutto._typing import AId, AvId, BvId, CId, EpisodeId
from yutto.exceptions import NotFoundError
from yutto.utils.fetcher import Fetcher


class PageInfo(TypedDict):
    part: str
    first_frame: Optional[str]


class VideoInfo(TypedDict):
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
    pages: list[PageInfo]


async def get_video_info(session: ClientSession, avid: AvId) -> VideoInfo:
    regex_ep = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")
    info_api = "http://api.bilibili.com/x/web-interface/view?aid={aid}&bvid={bvid}"
    res_json = await Fetcher.fetch_json(session, info_api.format(**avid.to_dict()))
    if res_json is None:
        raise NotFoundError(f"无法该视频 {avid} 信息")
    res_json_data = res_json.get("data")
    if res_json["code"] == 62002:
        raise NotFoundError(f"无法下载该视频 {avid}，原因：{res_json['message']}")
    if res_json["code"] == -404:
        raise NotFoundError(f"啊叻？视频 {avid} 不见了诶")
    assert res_json_data is not None, "响应数据无 data 域"
    episode_id = EpisodeId("")
    if res_json_data.get("redirect_url") and (ep_match := regex_ep.match(res_json_data["redirect_url"])):
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
        "pubdate": res_json_data["pubdate"],
        "description": res_json_data["desc"],
        "pages": [
            {
                "part": page["part"],
                "first_frame": page.get("first_frame"),
            }
            for page in res_json_data["pages"]
        ],
    }


async def is_vip(session: ClientSession) -> bool:
    info_api = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(session, info_api)
    assert res_json is not None
    res_json_data = res_json.get("data")
    if res_json_data.get("vipStatus") == 1:
        return True
    return False
