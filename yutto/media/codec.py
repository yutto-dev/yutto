from typing import Literal
from yutto.utils.priority import gen_priority_sequence


VideoCodecId = Literal[7, 12, 13]
VideoCodec = Literal["avc", "hevc", "av1"]
AudioCodecId = Literal[0]
AudioCodec = Literal["mp4a"]

video_codec_priority_default: list[VideoCodec] = ["avc", "hevc", "av1"]
audio_codec_priority_default: list[AudioCodec] = ["mp4a"]

video_codec_map: dict[VideoCodecId, VideoCodec] = {
    7: "avc",
    12: "hevc",
    13: "av1",  # Example: BV1w34y1q7HY
}

audio_codec_map: dict[AudioCodecId, AudioCodec] = {
    0: "mp4a",
}


def gen_vcodec_priority(video_codec: VideoCodec) -> list[VideoCodec]:
    """生成视频编码优先级序列"""

    choice = video_codec_priority_default.index(video_codec)
    return [
        video_codec_priority_default[idx] for idx in gen_priority_sequence(choice, len(video_codec_priority_default))
    ]


def gen_acodec_priority(audio_codec: AudioCodec) -> list[AudioCodec]:
    """生成音频编码优先级序列"""

    choice = audio_codec_priority_default.index(audio_codec)
    return [
        audio_codec_priority_default[idx] for idx in gen_priority_sequence(choice, len(audio_codec_priority_default))
    ]
