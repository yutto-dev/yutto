from enum import Enum
from typing import Literal

from yutto.utils.priority import gen_priority_sequence


class Media(Enum):
    VIDEO = 0
    AUDIO = 30200


VideoQuality = Literal[127, 126, 125, 120, 116, 112, 80, 74, 64, 32, 16]
AudioQuality = Literal[30280, 30232, 30216]

video_quality_priority_default: list[VideoQuality] = [127, 126, 125, 120, 116, 112, 80, 74, 64, 32, 16]
audio_quality_priority_default: list[AudioQuality] = [30280, 30232, 30216]

video_quality_map = {
    127: {
        "description": "8K 超高清",
        "width": 7680,
        "height": 4320,
    },  # Example: BV1KS4y197BN
    126: {
        "description": "杜比视界",
        "width": 3840,
        "height": 2160,
    },  # Example: BV1eV411W7tt
    125: {
        "description": "HDR 真彩",
        "width": 3840,
        "height": 2160,
    },
    120: {
        "description": "4K 超清",
        "width": 3840,
        "height": 2160,
    },
    116: {
        "description": "1080P 60帧",
        "width": 1920,
        "height": 1080,
    },
    112: {
        "description": "1080P 高码率",
        "width": 1920,
        "height": 1080,
    },
    80: {
        "description": "1080P 高清",
        "width": 1920,
        "height": 1080,
    },
    74: {
        "description": "720P 60帧",
        "width": 1280,
        "height": 720,
    },
    64: {
        "description": "720P 高清",
        "width": 1280,
        "height": 720,
    },
    32: {
        "description": "480P 清晰",
        "width": 852,
        "height": 480,
    },
    16: {
        "description": "360P 流畅",
        "width": 640,
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
    0: {
        "description": "Unknown",
        "bitrate": 0,
    },
}


def gen_video_quality_priority(quality: VideoQuality) -> list[VideoQuality]:
    choice = video_quality_priority_default.index(quality)
    return [
        video_quality_priority_default[idx]
        for idx in gen_priority_sequence(choice, len(video_quality_priority_default))
    ]


def gen_audio_quality_priority(quality: AudioQuality) -> list[AudioQuality]:
    choice = audio_quality_priority_default.index(quality)
    return [
        audio_quality_priority_default[idx]
        for idx in gen_priority_sequence(choice, len(audio_quality_priority_default))
    ]
