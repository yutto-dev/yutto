from typing import Optional, TypeVar

from yutto.api.acg_video import AudioUrlMeta, VideoUrlMeta
from yutto.media.codec import AudioCodec, VideoCodec, gen_acodec_priority, gen_vcodec_priority
from yutto.media.quality import AudioQuality, VideoQuality, gen_audio_quality_priority, gen_video_quality_priority


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
