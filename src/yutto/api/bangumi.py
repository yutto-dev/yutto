from __future__ import annotations

import re
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

from returns.result import Failure

from yutto.core.operation import ReportLevel, emit_download_report
from yutto.exceptions import NoAccessPermissionError, UnSupportedTypeError
from yutto.media.codec import audio_codec_map, video_codec_map
from yutto.types import (
    AudioUrlMeta,
    BvId,
    CId,
    EpisodeId,
    SeasonId,
    VideoUrlMeta,
    format_ids,
)
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result
from yutto.utils.functional import data_has_chained_keys
from yutto.utils.metadata import Actor, MetaData
from yutto.utils.time import get_time_stamp_by_now

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.types import (
        AvId,
        MediaId,
        MultiLangSubtitle,
    )


class _BangumiUpInfo(TypedDict):
    mid: int
    uname: str
    avatar: str


class _BangumiEpisode(TypedDict):
    title: str
    long_title: str
    cid: int
    id: int
    bvid: str
    badge: str
    share_copy: str
    cover: str
    pub_time: int
    duration: int


class _BangumiSection(TypedDict):
    type: int
    episodes: list[_BangumiEpisode]


class _BangumiSeason(TypedDict):
    title: str
    episodes: list[_BangumiEpisode]
    evaluate: str
    styles: list[str]
    section: NotRequired[list[_BangumiSection]]
    up_info: NotRequired[_BangumiUpInfo]


class BangumiListItem(TypedDict):
    id: int
    name: str
    cid: CId
    episode_id: EpisodeId
    avid: AvId
    duration: int
    is_section: bool  # 是否属于专区
    is_preview: bool
    metadata: MetaData


class BangumiList(TypedDict):
    title: str
    pages: list[BangumiListItem]


async def get_season_id_by_media_id(scope: ExecutionScope, media_id: MediaId) -> SeasonId:
    media_api = f"https://api.bilibili.com/pgc/review/user?media_id={media_id}"
    res_json = unwrap_fetch_result(await Fetcher.fetch_json(scope, media_api))
    return SeasonId(str(res_json["result"]["media"]["season_id"]))


async def get_season_id_by_episode_id(scope: ExecutionScope, episode_id: EpisodeId) -> SeasonId:
    episode_api = f"https://api.bilibili.com/pgc/view/web/season?ep_id={episode_id}"
    res_json = unwrap_fetch_result(await Fetcher.fetch_json(scope, episode_api))
    return SeasonId(str(res_json["result"]["season_id"]))


async def get_bangumi_list(scope: ExecutionScope, season_id: SeasonId) -> BangumiList:
    list_api = "http://api.bilibili.com/pgc/view/web/season?season_id={season_id}"
    list_result = await Fetcher.fetch_json(scope, list_api.format(season_id=season_id))
    if isinstance(list_result, Failure):
        raise NoAccessPermissionError(f"无法解析该番剧列表（season_id: {season_id}）") from list_result.failure()
    resp_json = list_result.unwrap()
    if resp_json.get("result") is None:
        raise NoAccessPermissionError(f"无法解析该番剧列表（season_id: {season_id}），原因：{resp_json.get('message')}")
    result = cast("_BangumiSeason", resp_json["result"])
    section_episodes = []
    for section in result.get("section", []):
        if section["type"] != 5:
            # 如 https://www.bilibili.com/bangumi/play/ep409825 中的「次元发电机采访」
            # 和 https://www.bilibili.com/bangumi/play/ep424859 中的「编辑推荐」
            section_episodes += section["episodes"]
    return BangumiList(
        title=result["title"],
        pages=[
            BangumiListItem(
                id=i + 1,
                name=_bangumi_episode_title(item["title"], item["long_title"]),
                cid=CId(str(item["cid"])),
                episode_id=EpisodeId(str(item["id"])),
                avid=BvId(item["bvid"]),
                duration=item["duration"],
                is_section=i >= len(result["episodes"]),
                is_preview=item["badge"] == "预告",  # 并不是一种鲁棒的方式，但目前貌似没有更好的方式了
                metadata=_parse_bangumi_metadata(
                    item,
                    evaluate=result["evaluate"],
                    styles=result["styles"],
                    up_info=result.get("up_info"),
                ),
            )
            for i, item in enumerate(result["episodes"] + section_episodes)
        ],
    )


async def get_bangumi_playurl(
    scope: ExecutionScope, avid: AvId, cid: CId
) -> tuple[list[VideoUrlMeta], list[AudioUrlMeta]]:
    play_api = "https://api.bilibili.com/pgc/player/web/v2/playurl?avid={aid}&bvid={bvid}&cid={cid}&qn=127&fnver=0&fnval=4048&fourk=1&support_multi_audio=true&from_client=BROWSER"

    play_result = await Fetcher.fetch_json(scope, play_api.format(**avid.to_dict(), cid=cid))
    if isinstance(play_result, Failure):
        raise NoAccessPermissionError(f"无法获取该视频链接（{format_ids(avid, cid)}）") from play_result.failure()
    resp_json = play_result.unwrap()
    if resp_json.get("result") is None or resp_json["result"].get("video_info") is None:
        raise NoAccessPermissionError(
            f"无法获取该视频链接（{format_ids(avid, cid)}），原因：{resp_json.get('message')}"
        )
    video_info = resp_json["result"]["video_info"]
    if video_info["is_preview"] == 1:
        # Maybe always 0 in v2 API
        emit_download_report(
            f"视频（{format_ids(avid, cid)}）是预览视频（疑似未登录或非大会员用户）",
            ReportLevel.WARNING,
        )
    if video_info.get("dash") is None:
        raise UnSupportedTypeError(f"该视频（{format_ids(avid, cid)}）尚不支持 DASH 格式")

    videos: list[VideoUrlMeta] = [
        VideoUrlMeta(
            url=video["base_url"],
            mirrors=video["backup_url"] if video["backup_url"] is not None else [],
            codec=video_codec_map[video["codecid"]],
            width=video["width"],
            height=video["height"],
            quality=video["id"],
        )
        for video in video_info["dash"]["video"]
    ]
    audios: list[AudioUrlMeta] = [
        AudioUrlMeta(
            url=audio["base_url"],
            mirrors=audio["backup_url"] if audio["backup_url"] is not None else [],
            codec=audio_codec_map[audio["codecid"]],
            width=0,
            height=0,
            quality=audio["id"],
        )
        for audio in video_info["dash"]["audio"]
    ]
    if video_info["dash"]["dolby"] is not None and video_info["dash"]["dolby"]["audio"] is not None:
        dolby_audios_json = video_info["dash"]["dolby"]["audio"]
        audios.extend(
            AudioUrlMeta(
                url=dolby_audio_json["base_url"],
                mirrors=dolby_audio_json["backup_url"] if dolby_audio_json["backup_url"] is not None else [],
                codec="eac3",  # TODO: 由于这里的 codecid 仍然是 0，所以无法通过 audio_codec_map 转换，暂时直接硬编码
                width=0,
                height=0,
                quality=dolby_audio_json["id"],
            )
            for dolby_audio_json in dolby_audios_json
        )
    return (videos, audios)


async def get_bangumi_subtitles(scope: ExecutionScope, avid: AvId, cid: CId) -> list[MultiLangSubtitle]:
    subtitle_api = "https://api.bilibili.com/x/player/wbi/v2?aid={aid}&bvid={bvid}&cid={cid}"
    subtitle_url = subtitle_api.format(**avid.to_dict(), cid=cid)
    subtitles_json_info = (await Fetcher.fetch_json(scope, subtitle_url)).value_or(None)
    if subtitles_json_info is None:
        return []
    if not data_has_chained_keys(subtitles_json_info, ["data", "subtitle", "subtitles"]):
        emit_download_report(
            f"无法获取该视频的字幕（{format_ids(avid, cid)}），原因：{subtitles_json_info.get('message')}",
            ReportLevel.WARNING,
        )
        return []
    subtitles_info = subtitles_json_info["data"]["subtitle"]
    results: list[MultiLangSubtitle] = []
    for sub_info in subtitles_info["subtitles"]:
        subtitle_url = sub_info["subtitle_url"]

        # 检查 subtitle_url 是否有效
        if subtitle_url is None or not subtitle_url.strip():
            emit_download_report(
                f"跳过无效的字幕URL（{format_ids(avid, cid)}），语言：{sub_info.get('lan_doc', '未知')}",
                ReportLevel.WARNING,
            )
            continue

        subtitle_text = (await Fetcher.fetch_json(scope, "https:" + subtitle_url)).value_or(None)
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


def _parse_bangumi_actor(up_info: _BangumiUpInfo | None) -> list[Actor]:
    if up_info is None:
        return []
    return [
        Actor(
            name=up_info["uname"],
            role="UP主",
            thumb=up_info["avatar"],
            profile=f"https://space.bilibili.com/{up_info['mid']}",
            order=0,
        )
    ]


def _parse_bangumi_metadata(
    item: _BangumiEpisode,
    *,
    evaluate: str,
    styles: list[str],
    up_info: _BangumiUpInfo | None,
) -> MetaData:
    plot = evaluate or item["share_copy"]
    return MetaData(
        title=_bangumi_episode_title(item["title"], item["long_title"]),
        show_title=item["share_copy"],
        plot=plot,
        thumb=item["cover"],
        premiered=item["pub_time"],
        dateadded=get_time_stamp_by_now(),
        source="",  # TODO
        actor=_parse_bangumi_actor(up_info),
        genre=[],  # TODO
        tag=styles,
        website="",  # TODO
        original_filename="",  # TODO
        chapter_info_data=[],  # There are no chapter info in bangumi for now
    )
