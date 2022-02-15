import re
from typing import Any, TypedDict

from aiohttp import ClientSession

from yutto.exceptions import NoAccessPermissionError, UnSupportedTypeError
from yutto.bilibili_typing.codec import audio_codec_map, video_codec_map
from yutto._typing import AudioUrlMeta, AvId, BvId, CId, EpisodeId, MediaId, MultiLangSubtitle, SeasonId, VideoUrlMeta
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.metadata import MetaData
from yutto.utils.time import get_time_str_by_now, get_time_str_by_stamp


class BangumiListItem(TypedDict):
    id: int
    name: str
    cid: CId
    episode_id: EpisodeId
    avid: AvId
    is_section: bool  # 是否属于专区
    metadata: MetaData


class BangumiList(TypedDict):
    title: str
    pages: list[BangumiListItem]


async def get_season_id_by_media_id(session: ClientSession, media_id: MediaId) -> SeasonId:
    home_url = "https://www.bilibili.com/bangumi/media/md{media_id}".format(media_id=media_id)
    season_id = SeasonId("")
    regex_season_id = re.compile(r'"param":{"season_id":(\d+),"season_type":\d+}')
    home_page = await Fetcher.fetch_text(session, home_url)
    assert home_page is not None
    if match_obj := regex_season_id.search(home_page):
        season_id = match_obj.group(1)
    return SeasonId(str(season_id))


async def get_season_id_by_episode_id(session: ClientSession, episode_id: EpisodeId) -> SeasonId:
    home_url = "https://www.bilibili.com/bangumi/play/ep{episode_id}".format(episode_id=episode_id)
    season_id = SeasonId("")
    regex_season_id = re.compile(r'"id":\d+,"ssId":(\d+)')
    home_page = await Fetcher.fetch_text(session, home_url)
    assert home_page is not None
    if match_obj := regex_season_id.search(home_page):
        season_id = match_obj.group(1)
    return SeasonId(str(season_id))


async def get_bangumi_list(session: ClientSession, season_id: SeasonId) -> BangumiList:
    list_api = "http://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
    resp_json = await Fetcher.fetch_json(session, list_api.format(season_id=season_id))
    assert resp_json is not None
    result = resp_json["result"]
    section_episodes = []
    for section in result.get("section", []):
        section_episodes += section["episodes"]
    return {
        "title": result["title"],
        "pages": [
            {
                "id": i + 1,
                "name": _bangumi_episode_title(item["title"], item["long_title"]),
                "cid": CId(str(item["cid"])),
                "episode_id": EpisodeId(str(item["id"])),
                "avid": BvId(item["bvid"]),
                "is_section": i >= len(result["episodes"]),
                "metadata": _parse_bangumi_metadata(item),
            }
            for i, item in enumerate(result["episodes"] + section_episodes)
        ],
    }


async def get_bangumi_playurl(
    session: ClientSession, avid: AvId, episode_id: EpisodeId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = "https://api.bilibili.com/pgc/player/web/playurl?avid={aid}&bvid={bvid}&ep_id={episode_id}&cid={cid}&qn=127&fnver=0&fnval=16&fourk=1"

    resp_json = await Fetcher.fetch_json(session, play_api.format(**avid.to_dict(), cid=cid, episode_id=episode_id))
    if resp_json is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}）")
    if resp_json.get("result") is None:
        raise NoAccessPermissionError(f"无法获取该视频链接（avid: {avid}, cid: {cid}），原因：{resp_json.get('message')}")
    if resp_json["result"]["is_preview"] == 1:
        Logger.warning(f"视频（avid: {avid}, cid: {cid}）是预览视频（疑似未登录或非大会员用户）")
    if resp_json["result"].get("dash") is None:
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
            for video in resp_json["result"]["dash"]["video"]
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
            for audio in resp_json["result"]["dash"]["audio"]
        ],
    )


async def get_bangumi_subtitles(session: ClientSession, avid: AvId, cid: CId) -> list[MultiLangSubtitle]:
    subtitile_api = "https://api.bilibili.com/x/player/v2?cid={cid}&aid={aid}&bvid={bvid}"
    subtitile_url = subtitile_api.format(**avid.to_dict(), cid=cid)
    subtitles_json_info = await Fetcher.fetch_json(session, subtitile_url)
    if subtitles_json_info is None:
        return []
    subtitles_info = subtitles_json_info["data"]["subtitle"]
    results: list[MultiLangSubtitle] = []
    for sub_info in subtitles_info["subtitles"]:
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


def _bangumi_episode_title(title: str, extra_title: str) -> str:
    title_parts: list[str] = []
    if re.match(r"^\d*\.?\d*$", title):
        title_parts.append(f"第{title}话")
    else:
        title_parts.append(title)

    if extra_title:
        title_parts.append(extra_title)

    return " ".join(title_parts)


def _parse_bangumi_metadata(item: dict[str, Any]) -> MetaData:

    return MetaData(
        title=_bangumi_episode_title(item["title"], item["long_title"]),
        show_title=item["share_copy"],
        plot=item["share_copy"],
        thumb=item["cover"],
        premiered=get_time_str_by_stamp(item["pub_time"]),
        dataadded=get_time_str_by_now(),
        source="",  # TODO
        original_filename="",  # TODO
    )
