import re
from typing import Literal, TypedDict

from aiohttp import ClientSession

from yutto.api.types import (
    AudioUrlMeta,
    AvId,
    BvId,
    CId,
    EpisodeId,
    MediaId,
    MultiLangSubtitle,
    NoAccessError,
    SeasonId,
    UnSupportedTypeError,
    VideoUrlMeta,
)
from yutto.media.codec import VideoCodec
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher


class BangumiListItem(TypedDict):
    id: int
    name: str
    cid: CId
    episode_id: EpisodeId
    avid: AvId
    is_section: bool  # 是否属于专区


async def get_season_id_by_media_id(session: ClientSession, media_id: MediaId) -> SeasonId:
    home_url = "https://www.bilibili.com/bangumi/media/md{media_id}".format(media_id=media_id)
    season_id = SeasonId("")
    regex_season_id = re.compile(r'"param":{"season_id":(\d+),"season_type":\d+}')
    if match_obj := regex_season_id.search(await Fetcher.fetch_text(session, home_url)):
        season_id = match_obj.group(1)
    return SeasonId(str(season_id))


async def get_season_id_by_episode_id(session: ClientSession, episode_id: EpisodeId) -> SeasonId:
    home_url = "https://www.bilibili.com/bangumi/play/ep{episode_id}".format(episode_id=episode_id)
    season_id = SeasonId
    regex_season_id = re.compile(r'"id":\d+,"ssId":(\d+)')
    if match_obj := regex_season_id.search(await Fetcher.fetch_text(session, home_url)):
        season_id = match_obj.group(1)
    return SeasonId(str(season_id))


async def get_bangumi_title(session: ClientSession, season_id: SeasonId) -> str:
    play_url = "https://www.bilibili.com/bangumi/play/ss{season_id}".format(season_id=season_id)
    regex_title = re.compile(r'<a href=".+" target="_blank" title="(.*?)" class="media-title">(?P<title>.*?)</a>')
    if match_obj := regex_title.search(await Fetcher.fetch_text(session, play_url)):
        title = match_obj.group("title")
    else:
        title = "呐，我也不知道是什么标题呢～"
    return title


async def get_bangumi_list(session: ClientSession, season_id: SeasonId) -> list[BangumiListItem]:
    list_api = "http://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
    resp_json = await Fetcher.fetch_json(session, list_api.format(season_id=season_id))
    result = resp_json["result"]
    section_episodes = []
    for section in result.get("section", []):
        section_episodes += section["episodes"]
    return [
        {
            "id": i + 1,
            "name": " ".join(
                [
                    "第{}话".format(item["title"]) if re.match(r"^\d*\.?\d*$", item["title"]) else item["title"],
                    item["long_title"],
                ]
            ),
            "cid": CId(str(item["cid"])),
            "episode_id": EpisodeId(str(item["id"])),
            "avid": BvId(item["bvid"]),
            "is_section": i >= len(result["episodes"]),
        }
        for i, item in enumerate(result["episodes"] + section_episodes)
    ]


async def get_bangumi_playurl(
    session: ClientSession, avid: AvId, episode_id: EpisodeId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = "https://api.bilibili.com/pgc/player/web/playurl?avid={aid}&bvid={bvid}&ep_id={episode_id}&cid={cid}&qn=125&fnver=0&fnval=16&fourk=1"
    codecid_map: dict[Literal[7, 12], VideoCodec] = {7: "avc", 12: "hevc"}

    async with session.get(
        play_api.format(**avid.to_dict(), cid=cid, episode_id=episode_id), proxy=Fetcher.proxy
    ) as resp:
        if not resp.ok:
            raise NoAccessError("无法下载该视频（cid: {cid}）".format(cid=cid))
        resp_json = await resp.json()
        if resp_json.get("result") is None:
            raise NoAccessError("无法下载该视频（cid: {cid}），原因：{msg}".format(cid=cid, msg=resp_json.get("message")))
        if resp_json["result"].get("dash") is None:
            raise UnSupportedTypeError("该视频（cid: {cid}）尚不支持 DASH 格式".format(cid=cid))
        if resp_json["result"]["is_preview"] == 1:
            Logger.warning("视频（cid: {cid}）是预览视频".format(cid=cid))
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
                for video in resp_json["result"]["dash"]["video"]
            ],
            [
                {
                    "url": audio["base_url"],
                    "mirrors": audio["backup_url"] if audio["backup_url"] is not None else [],
                    "codec": "mp4a",
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
    subtitles_info = (await Fetcher.fetch_json(session, subtitile_url))["data"]["subtitle"]
    return [
        # fmt: off
        {
            "lang": sub_info["lan_doc"],
            "lines": (await Fetcher.fetch_json(session, "https:" + sub_info["subtitle_url"]))["body"]
        }
        for sub_info in subtitles_info["subtitles"]
        # fmt: on
    ]
