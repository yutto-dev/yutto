import json
import re
from typing import TypedDict

from aiohttp import ClientSession

from yutto.api.info import get_video_info, VideoInfo, PageInfo
from yutto.exceptions import NoAccessPermissionError, UnSupportedTypeError
from yutto.bilibili_typing.codec import audio_codec_map, video_codec_map
from yutto._typing import AudioUrlMeta, AvId, CId, MultiLangSubtitle, VideoUrlMeta
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.metadata import MetaData
from yutto.utils.time import get_time_str_by_now, get_time_str_by_stamp


class AcgVideoListItem(TypedDict):
    id: int
    name: str
    avid: AvId
    cid: CId
    metadata: MetaData


class AcgVideoList(TypedDict):
    title: str
    pubdate: str
    pages: list[AcgVideoListItem]


async def get_acg_video_list(session: ClientSession, avid: AvId) -> AcgVideoList:
    video_info = await get_video_info(session, avid)
    result: AcgVideoList = {
        "title": video_info["title"],
        "pubdate": get_time_str_by_stamp(video_info["pubdate"], "%Y-%m-%d"),  # TODO: 可自由定制
        "pages": [],
    }
    list_api = "https://api.bilibili.com/x/player/pagelist?aid={aid}&bvid={bvid}&jsonp=jsonp"
    res_json = await Fetcher.fetch_json(session, list_api.format(**avid.to_dict()))
    if res_json is None or res_json.get("data") is None:
        Logger.warning(f"啊叻？视频 {avid} 不见了诶")
        return result
    result["pages"] = [
        {
            "id": i + 1,
            "name": item["part"],
            "avid": avid,
            "cid": CId(str(item["cid"])),
            "metadata": _parse_acg_video_metadata(video_info, page_info),
        }
        for i, (item, page_info) in enumerate(zip(res_json["data"], video_info["pages"]))
    ]
    return result


async def get_acg_video_playurl(
    session: ClientSession, avid: AvId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    # 4048 = 16(useDash) | 64(useHDR) | 128(use4K) | 256(useDolby) | 512(useXXX) | 1024(use8K) | 2048(useAV1)
    play_api = "https://api.bilibili.com/x/player/playurl?avid={aid}&bvid={bvid}&cid={cid}&qn=127&type=&otype=json&fnver=0&fnval=4048&fourk=1"

    resp_json = await Fetcher.fetch_json(session, play_api.format(**avid.to_dict(), cid=cid))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}）")
    if resp_json.get("data") is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}），原因：{resp_json.get('message')}")
    if resp_json["data"].get("dash") is None:
        raise UnSupportedTypeError(f"该视频（avid: {avid}, cid: {cid}）尚不支持 DASH 格式")
    # TODO: 处理 resp_json["data"]["dash"]["dolby"]，应当是 Dolby 的音频流
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
        ]
        if resp_json["data"]["dash"]["video"]
        else [],
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
        else [],
    )


async def get_acg_video_subtitles(session: ClientSession, avid: AvId, cid: CId) -> list[MultiLangSubtitle]:
    subtitile_api = "https://api.bilibili.com/x/player.so?aid={aid}&bvid={bvid}&id=cid:{cid}"
    subtitile_url = subtitile_api.format(**avid.to_dict(), cid=cid)
    res_text = await Fetcher.fetch_text(session, subtitile_url)
    if res_text is None:
        return []
    if subtitle_json_text_match := re.search(r"<subtitle>(.+)</subtitle>", res_text):
        subtitle_json = json.loads(subtitle_json_text_match.group(1))
        results: list[MultiLangSubtitle] = []
        for sub_info in subtitle_json["subtitles"]:
            subtitle_text = await Fetcher.fetch_json(session, "https:" + sub_info["subtitle_url"])
            if subtitle_text is None:
                continue
            results.append(
                {
                    "lang": sub_info["lan_doc"],
                    "lines": subtitle_text["body"],
                }
            )
        return results
    return []


def _parse_acg_video_metadata(video_info: VideoInfo, page_info: PageInfo) -> MetaData:
    return MetaData(
        title=page_info["part"],
        show_title=page_info["part"],
        plot=video_info["description"],
        thumb=page_info["first_frame"] if page_info["first_frame"] is not None else video_info["picture"],
        premiered=get_time_str_by_stamp(video_info["pubdate"]),
        dataadded=get_time_str_by_now(),
        source="",  # TODO
        original_filename="",  # TODO
    )
