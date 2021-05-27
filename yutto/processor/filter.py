import re
import sys
from typing import Optional, TypeVar

from yutto.api.acg_video import AudioUrlMeta, VideoUrlMeta
from yutto.media.codec import AudioCodec, VideoCodec, gen_acodec_priority, gen_vcodec_priority
from yutto.media.quality import AudioQuality, VideoQuality, gen_audio_quality_priority, gen_video_quality_priority
from yutto.utils.console.logger import Logger


def select_video(
    videos: list[VideoUrlMeta],
    require_video: bool = True,
    video_quality: VideoQuality = 125,
    video_codec: VideoCodec = "hevc",
) -> Optional[VideoUrlMeta]:
    if not require_video:
        return None

    video_quality_priority = gen_video_quality_priority(video_quality)
    video_codec_priority = gen_vcodec_priority(video_codec)

    # fmt: off
    video_combined_priority = [
        (vqn, vcodec)
        for vqn in video_quality_priority
        for vcodec in video_codec_priority
    ]
    # fmt: on

    for vqn, vcodec in video_combined_priority:
        for video in videos:
            if video["quality"] == vqn and video["codec"] == vcodec:
                return video
    return None


def select_audio(
    audios: list[AudioUrlMeta],
    require_audio: bool = True,
    audio_quality: AudioQuality = 30280,
    audio_codec: AudioCodec = "mp4a",
) -> Optional[AudioUrlMeta]:
    if not require_audio:
        return None

    audio_quality_priority = gen_audio_quality_priority(audio_quality)
    audio_codec_priority = gen_acodec_priority(audio_codec)

    # fmt: off
    audio_combined_priority = [
        (aqn, acodec)
        for aqn in audio_quality_priority
        for acodec in audio_codec_priority
    ]
    # fmt: on

    for aqn, acodec in audio_combined_priority:
        for audio in audios:
            if audio["quality"] == aqn and audio["codec"] == acodec:
                return audio
    return None


T = TypeVar("T")


def filter_none_value(l: list[Optional[T]]) -> list[T]:
    result: list[T] = []
    for item in l:
        if item is not None:
            result.append(item)
    return result
    # ? 不清楚直接这么写为什么类型不匹配
    # return list(filter(lambda x: x is not None, l))


def check_episodes(episodes_str: str) -> bool:
    return bool(re.match(r"([\-\d\^\$]+(~[\-\d\^\$]+)?)(,[\-\d\^\$]+(~[\-\d\^\$]+)?)*", episodes_str))


def parse_episodes(episodes_str: str, total: int) -> list[int]:
    """ 将选集字符串转为列表（标号从 1 开始） """

    if total == 0:
        Logger.warning("该剧集列表无任何剧集，猜测正片尚未上线，如果想要下载 PV 等特殊剧集，请添加参数 -s")
        return []

    def resolve_negetive(value: int) -> int:
        if value == 0:
            Logger.error("不可使用 0 作为剧集号（剧集号从 1 开始计算）")
            sys.exit(1)
        return value if value > 0 else value + total + 1

    # 解析字符串为列表
    Logger.info("全 {} 话".format(total))
    if check_episodes(episodes_str):
        episodes_str = episodes_str.replace("^", "1")
        episodes_str = episodes_str.replace("$", "-1")
        episode_list: list[int] = []
        for episode_item in episodes_str.split(","):
            if "~" in episode_item:
                start, end = episode_item.split("~")
                start, end = int(start), int(end)
                start, end = resolve_negetive(start), resolve_negetive(end)
                if not (end >= start):
                    Logger.error("终点值（{}）应不小于起点值（{}）".format(end, start))
                    sys.exit(1)
                episode_list.extend(list(range(start, end + 1)))
            else:
                episode_item = int(episode_item)
                episode_item = resolve_negetive(episode_item)
                episode_list.append(episode_item)
    else:
        episode_list = []

    episode_list = sorted(list(set(episode_list)))

    # 筛选满足条件的剧集
    out_of_range: list[int] = []
    episodes: list[int] = []
    for episode in episode_list:
        if episode in range(1, total + 1):
            if episode not in episodes:
                episodes.append(episode)
        else:
            out_of_range.append(episode)
    if out_of_range:
        Logger.warning("剧集 {} 不存在".format(",".join(list(map(str, out_of_range)))))

    Logger.info("已选择第 {} 话".format(",".join(list(map(str, episodes)))))
    if not episodes:
        Logger.warning("没有选中任何剧集")
    return episodes
