from typing import Any, Literal

VideoCodec = Literal["hevc", "avc"]
AudioCodec = Literal["mp4a"]


def gen_vcodec_priority(video_codec: VideoCodec) -> list[VideoCodec]:
    """ 生成视频编码优先级序列 """

    return ["hevc", "avc"] if video_codec == "hevc" else ["avc", "hevc"]


def gen_acodec_priority(audio_codec: AudioCodec) -> list[AudioCodec]:
    """ 生成视频编码优先级序列 """

    return ["mp4a"]
