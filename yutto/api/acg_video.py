import json
import re
from typing import Any, TypedDict

from aiohttp import ClientSession

from yutto.api.types import AId, AvId, BvId, CId, EpisodeId
from yutto.urlparser import regexp_bangumi_ep
from yutto.utils.fetcher import Fetcher


class HttpStatusError(Exception):
    pass


class NoAccessError(Exception):
    pass


class UnSupportedTypeError(Exception):
    pass


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


async def get_acg_video_title(session: ClientSession, avid: AvId) -> str:
    return (await get_video_info(session, avid))["title"]


async def get_acg_video_list(session: ClientSession, avid: AvId) -> list[dict[str, Any]]:
    list_api = "https://api.bilibili.com/x/player/pagelist?aid={aid}&bvid={bvid}&jsonp=jsonp"
    res_json = await Fetcher.fetch_json(session, list_api.format(**avid.to_dict()))
    return [
        # fmt: off
        {
            "id": i + 1,
            "name": item["part"],
            "cid": str(item["cid"])
        }
        for i, item in enumerate(res_json["data"])
    ]


async def get_acg_video_playurl(
    session: ClientSession, avid: AvId, cid: CId
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    play_api = "https://api.bilibili.com/x/player/playurl?avid={aid}&bvid={bvid}&cid={cid}&qn=125&type=&otype=json&fnver=0&fnval=80&fourk=1"

    async with session.get(play_api.format(**avid.to_dict(), cid=cid)) as resp:
        if not resp.ok:
            raise NoAccessError("无法下载该视频（cid: {cid}）".format(cid=cid))
        resp_json = await resp.json()
        if resp_json["data"].get("dash") is None:
            raise UnSupportedTypeError("该视频（cid: {cid}）尚不支持 DASH 格式".format(cid=cid))
        return (
            [
                {
                    "url": video["base_url"],
                    "mirrors": video["backup_url"],
                    "codec": {7: "avc", 12: "hevc"}[video["codecid"]],
                    "width": video["width"],
                    "height": video["height"],
                    "quality": video["id"],
                }
                for video in resp_json["data"]["dash"]["video"]
            ],
            [
                {
                    "url": audio["base_url"],
                    "mirrors": audio["backup_url"],
                    "codec": "mp4a",
                    "width": 0,
                    "height": 0,
                    "quality": audio["id"],
                }
                for audio in resp_json["data"]["dash"]["audio"]
            ],
        )


async def get_acg_video_subtitile(session: ClientSession, avid: AvId, cid: CId) -> list[dict[str, str]]:
    subtitile_api = "https://api.bilibili.com/x/player.so?aid={aid}&bvid={bvid}&id=cid:{cid}"
    subtitile_url = subtitile_api.format(**avid.to_dict(), cid=cid)
    res_text = await Fetcher.fetch_text(session, subtitile_url)
    if subtitle_json_text_match := re.search(r"<subtitle>(.+)</subtitle>", res_text):
        subtitle_json = json.loads(subtitle_json_text_match.group(1))
        return [
            # fmt: off
            {
                "lang": sub_info["lan_doc"],
                "lines": (await Fetcher.fetch_json(session, "https:" + sub_info["subtitle_url"]))["body"]
            }
            for sub_info in subtitle_json["subtitles"]
        ]
    else:
        return []
