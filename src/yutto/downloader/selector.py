from __future__ import annotations

from typing import TYPE_CHECKING

from yutto.bilibili_typing.codec import (
    AudioCodec,
    VideoCodec,
    gen_acodec_priority,
    gen_vcodec_priority,
)
from yutto.bilibili_typing.quality import (
    AudioQuality,
    VideoQuality,
    gen_audio_quality_priority,
    gen_video_quality_priority,
)

if TYPE_CHECKING:
    from yutto._typing import AudioUrlMeta, VideoUrlMeta


def select_video(
    videos: list[VideoUrlMeta],
    video_quality: VideoQuality = 127,
    video_codec: VideoCodec = "hevc",
    video_download_codec_priority: list[VideoCodec] | None = None,
) -> VideoUrlMeta | None:
    video_quality_priority = gen_video_quality_priority(video_quality)
    video_codec_priority = (
        gen_vcodec_priority(video_codec) if video_download_codec_priority is None else video_download_codec_priority
    )

    video_combined_priority = [
        (vqn, vcodec)
        for vqn in video_quality_priority
        # TODO: Dolby Selector
        for vcodec in video_codec_priority
    ]  # fmt: skip

    for vqn, vcodec in video_combined_priority:
        for video in videos:
            if video["quality"] == vqn and video["codec"] == vcodec:
                return video
    return None


def select_audio(
    audios: list[AudioUrlMeta],
    audio_quality: AudioQuality = 30280,
    audio_codec: AudioCodec = "mp4a",
) -> AudioUrlMeta | None:
    audio_quality_priority = gen_audio_quality_priority(audio_quality)
    audio_codec_priority = gen_acodec_priority(audio_codec)

    audio_combined_priority = [
        (aqn, acodec)
        for aqn in audio_quality_priority
        for acodec in audio_codec_priority
    ]  # fmt: skip

    for aqn, acodec in audio_combined_priority:
        for audio in audios:
            if audio["quality"] == aqn and audio["codec"] == acodec:
                return audio
    return None
