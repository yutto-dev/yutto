from __future__ import annotations

import pytest

from yutto.downloader.downloader import resolve_audio_save_codec

pytestmark = pytest.mark.processor


@pytest.mark.parametrize(
    ("audio_codec", "audio_save_codec", "container_suffix", "expected"),
    [
        # 单编码容器 + 默认 copy：自动转码（此前会在 FFmpeg 写头阶段失败）
        ("mp4a", "copy", ".mp3", "mp3"),
        ("flac", "copy", ".mp3", "mp3"),
        ("eac3", "copy", ".mp3", "mp3"),
        ("mp4a", "copy", ".flac", "flac"),
        ("eac3", "copy", ".flac", "flac"),
        ("flac", "copy", ".aac", "aac"),
        ("eac3", "copy", ".aac", "aac"),
        # 源编码本就能装入目标容器：保持 copy
        ("flac", "copy", ".flac", "copy"),
        ("mp4a", "copy", ".aac", "copy"),
        # 非单编码容器：行为不变
        ("mp4a", "copy", ".m4a", "copy"),
        ("flac", "copy", ".mkv", "copy"),
        ("mp4a", "copy", ".mp4", "copy"),
        # 源编码与保存编码一致：退化为 copy（原有行为）
        ("mp4a", "mp4a", ".m4a", "copy"),
        ("flac", "flac", ".flac", "copy"),
        # 用户显式指定的保存编码不受容器干预
        ("mp4a", "mp3", ".mp3", "mp3"),
        ("mp4a", "flac", ".flac", "flac"),
        ("mp4a", "aac", ".mp3", "aac"),
    ],
)
def test_resolve_audio_save_codec(audio_codec: str, audio_save_codec: str, container_suffix: str, expected: str):
    assert resolve_audio_save_codec(audio_codec, audio_save_codec, container_suffix) == expected
