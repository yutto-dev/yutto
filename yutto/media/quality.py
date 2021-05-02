from enum import Enum
from typing import Any, Literal


class Media(Enum):
    VIDEO = 0
    AUDIO = 30200


VideoQuality = Literal[125, 120, 116, 112, 80, 74, 64, 32, 16]
AudioQuality = Literal[30280, 30232, 30216]

video_quality_priority_default: list[VideoQuality] = [125, 120, 116, 112, 80, 74, 64, 32, 16]
audio_quality_priority_default: list[AudioQuality] = [30280, 30232, 30216]

video_quality_map = {
    125: {
        "description": "HDR 真彩",
        "width": 3840,
        "height": 1920,
    },
    120: {
        "description": "4K 超清",
        "width": 3840,
        "height": 1920,
    },
    116: {
        "description": "1080P 60帧",
        "width": 2160,
        "height": 1080,
    },
    112: {
        "description": "1080P 高码率",
        "width": 2160,
        "height": 1080,
    },
    80: {
        "description": "1080P 高清",
        "width": 2160,
        "height": 1080,
    },
    74: {
        "description": "720P 60帧",
        "width": 1440,
        "height": 720,
    },
    64: {
        "description": "720P 高清",
        "width": 1440,
        "height": 720,
    },
    32: {
        "description": "480P 清晰",
        "width": 960,
        "height": 480,
    },
    16: {
        "description": "360P 流畅",
        "width": 720,
        "height": 360,
    },
}

audio_quality_map = {
    30280: {
        "description": "320kbps",
        "bitrate": 320,
    },
    30232: {
        "description": "128kbps",
        "bitrate": 128,
    },
    30216: {
        "description": "64kbps",
        "bitrate": 64,
    },
    0: {"description": "Unknown", "bitrate": 0},
}


def gen_quality_priority(quality: Any, quality_priority: list[Any]) -> list[Any]:
    """ 根据默认先降后升的清晰度机制生成清晰度序列 """

    return quality_priority[quality_priority.index(quality) :] + list(
        reversed(quality_priority[: quality_priority.index(quality)])
    )


def gen_audio_quality_priority(quality: AudioQuality) -> list[AudioQuality]:
    return gen_quality_priority(quality, audio_quality_priority_default)


def gen_video_quality_priority(quality: VideoQuality) -> list[VideoQuality]:
    return gen_quality_priority(quality, video_quality_priority_default)
