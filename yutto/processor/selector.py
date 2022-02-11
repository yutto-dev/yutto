import re
import sys
from typing import Optional

from yutto.api.acg_video import AudioUrlMeta, VideoUrlMeta
from yutto.exceptions import ErrorCode
from yutto.bilibili_typing.codec import AudioCodec, VideoCodec, gen_acodec_priority, gen_vcodec_priority
from yutto.bilibili_typing.quality import (
    AudioQuality,
    VideoQuality,
    gen_audio_quality_priority,
    gen_video_quality_priority,
)
from yutto.utils.console.logger import Logger


def select_video(
    videos: list[VideoUrlMeta],
    require_video: bool = True,
    video_quality: VideoQuality = 127,
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
                # TODO: Dolby Support
                if video["quality"] == 126:
                    Logger.warning("目前仅支持杜比视界视频流下载，但可能无法达到在线观看的效果")
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


def validate_episodes_selection(episodes_str: str) -> bool:
    regex_number = r"(-?(0|[1-9]\d*))"
    regex_episode = rf"({regex_number}|\$|\^)"
    regex_range = rf"({regex_episode}|({regex_episode}?~{regex_episode}?))"
    regex_compose = rf"{regex_range}(,{regex_range})*"
    return bool(re.match(rf"{regex_compose}$", episodes_str))


def parse_episodes_selection(episodes_str: str, total: int) -> list[int]:
    """将选集字符串转为列表（标号从 1 开始）"""

    if total == 0:
        Logger.warning("该剧集列表无任何剧集，猜测正片尚未上线，如果想要下载 PV 等特殊剧集，请添加参数 -s")
        return []

    def resolve_negetive(value: int) -> int:
        if value == 0:
            Logger.error("不可使用 0 作为剧集号（剧集号从 1 开始计算）")
            sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
        return value if value > 0 else value + total + 1

    # 解析字符串为列表
    Logger.info(f"全 {total} 话")
    if validate_episodes_selection(episodes_str):
        if "^" in episodes_str:
            episodes_str = episodes_str.replace("^", "1")
            Logger.deprecated_warning("起始符语法糖 ^ 已经被弃用，将会在 2.0.0 正式版移除，请直接使用明确的剧集序号 1 代替，或者在使用范围时，起始为 1 时可以省略")
        episodes_str = episodes_str.replace("$", "-1")
        episode_list: list[int] = []
        for episode_item in episodes_str.split(","):
            if "~" in episode_item:
                splitted = episode_item.split("~")
                if len(splitted) != 2:
                    Logger.error("{} 选集参数每部分至多包含一个 ~".format(episode_item))
                    sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
                start, end = splitted
                start, end = "1" if not start else start, "-1" if not end else end
                start, end = int(start), int(end)
                start, end = resolve_negetive(start), resolve_negetive(end)
                if not (end >= start):
                    Logger.error("终点值（{}）应不小于起点值（{}）".format(end, start))
                    sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
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
