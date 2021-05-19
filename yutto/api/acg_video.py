import json
import re
from typing import Literal, TypedDict

from aiohttp import ClientSession

from yutto.api.info import get_video_info
from yutto.api.types import (
    AudioUrlMeta,
    AvId,
    CId,
    MultiLangSubtitle,
    NoAccessError,
    UnSupportedTypeError,
    VideoUrlMeta,
)
from yutto.media.codec import VideoCodec
from yutto.utils.fetcher import Fetcher


class AcgVideoListItem(TypedDict):
    id: int
    name: str
    cid: CId


async def get_acg_video_title(session: ClientSession, avid: AvId) -> str:
    return (await get_video_info(session, avid))["title"]


async def get_acg_video_list(session: ClientSession, avid: AvId) -> list[AcgVideoListItem]:
    list_api = "https://api.bilibili.com/x/player/pagelist?aid={aid}&bvid={bvid}&jsonp=jsonp"
    res_json = await Fetcher.fetch_json(session, list_api.format(**avid.to_dict()))
    return [
        # fmt: off
        {
            "id": i + 1,
            "name": item["part"],
            "cid": CId(str(item["cid"]))
        }
        # fmt: on
        for i, item in enumerate(res_json["data"])
    ]


async def get_acg_video_playurl(
    session: ClientSession, avid: AvId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = "https://api.bilibili.com/x/player/playurl?avid={aid}&bvid={bvid}&cid={cid}&qn=125&type=&otype=json&fnver=0&fnval=80&fourk=1"
    codecid_map: dict[Literal[7, 12], VideoCodec] = {7: "avc", 12: "hevc"}

    async with session.get(play_api.format(**avid.to_dict(), cid=cid), proxy=Fetcher.proxy) as resp:
        if not resp.ok:
            raise NoAccessError("无法下载该视频（cid: {cid}）".format(cid=cid))
        resp_json = await resp.json()
        if resp_json.get("data") is None:
            raise NoAccessError("无法下载该视频（cid: {cid}），原因：{msg}".format(cid=cid, msg=resp_json.get("message")))
        if resp_json["data"].get("dash") is None:
            raise UnSupportedTypeError("该视频（cid: {cid}）尚不支持 DASH 格式".format(cid=cid))
        return (
            [
                {
                    "url": video["base_url"],
                    "mirrors": video["backup_url"] if video["backup_url"] is not None else [],
                    "codec": codecid_map[video["codecid"]],
                    "width": video["width"],
                    "height": video["height"],
                    "quality": video["id"],
                }
                for video in resp_json["data"]["dash"]["video"]
            ]
            if resp_json["data"]["dash"]["video"]
            else [],
            [
                {
                    "url": audio["base_url"],
                    "mirrors": audio["backup_url"] if audio["backup_url"] is not None else [],
                    "codec": "mp4a",
                    "width": 0,
                    "height": 0,
                    "quality": audio["id"],
                }
                for audio in resp_json["data"]["dash"]["audio"]
            ]
            if resp_json["data"]["dash"]["audio"]
            else [],
        )


async def get_acg_video_subtitles(session: ClientSession, avid: AvId, cid: CId) -> list[MultiLangSubtitle]:
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
            # fmt: on
        ]
    else:
        return []
