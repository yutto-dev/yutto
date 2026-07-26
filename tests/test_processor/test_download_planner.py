from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from yutto.core.request import DownloadRequest
from yutto.core.result import ResolvedItem
from yutto.downloader.planner import DownloadPlanner
from yutto.types import AId, CId

if TYPE_CHECKING:
    from yutto.media.codec import AudioCodec, VideoCodec
    from yutto.types import AudioUrlMeta, EpisodeData, VideoUrlMeta

pytestmark = pytest.mark.processor


def make_video(codec: VideoCodec = "avc") -> VideoUrlMeta:
    return {
        "url": "https://signed.example.test/video?token=video-secret",
        "mirrors": ["https://mirror.example.test/video?token=mirror-secret"],
        "codec": codec,
        "width": 1920,
        "height": 1080,
        "quality": 80,
    }


def make_audio(codec: AudioCodec = "mp4a") -> AudioUrlMeta:
    return {
        "url": "https://signed.example.test/audio?token=audio-secret",
        "mirrors": ["https://mirror.example.test/audio?token=mirror-secret"],
        "codec": codec,
        "width": 0,
        "height": 0,
        "quality": 30280,
    }


def make_episode(
    *,
    videos: list[VideoUrlMeta] | None = None,
    audios: list[AudioUrlMeta] | None = None,
    path: Path = Path("series/episode"),
) -> EpisodeData:
    return {
        "info": {
            "listing": ResolvedItem(
                avid=AId("1"),
                cid=CId("1"),
                url="https://www.bilibili.com/video/av1?p=1",
                name=path.name,
                title=path.name,
                cover_url="",
                planned_path=path,
            ),
            "path": path,
        },
        "videos": videos or [],
        "audios": audios or [],
        "subtitles": [],
        "metadata": None,
        "danmaku": {"source_type": None, "save_type": None, "data": []},
        "cover_data": None,
        "chapter_info_data": [],
    }


def make_request(
    tmp_path: Path,
    *,
    video: bool,
    audio: bool,
    video_codec: VideoCodec = "avc",
    audio_codec: AudioCodec = "mp4a",
    video_save_codec: str = "copy",
    audio_save_codec: str = "copy",
    output_format: str = "infer",
    audio_only_format: str = "infer",
    use_output_as_temporary: bool = False,
) -> DownloadRequest:
    return DownloadRequest.model_validate(
        {
            "source": {"url": "BV1planner"},
            "resources": {
                "video": video,
                "audio": audio,
                "danmaku": False,
                "subtitle": False,
                "metadata": False,
                "cover": False,
                "chapter_info": False,
            },
            "stream": {
                "video_download_codec": video_codec,
                "video_save_codec": video_save_codec,
                "audio_download_codec": audio_codec,
                "audio_save_codec": audio_save_codec,
            },
            "output": {
                "directory": tmp_path / "output",
                "temporary_directory": None if use_output_as_temporary else tmp_path / "temporary",
                "format": output_format,
                "audio_only_format": audio_only_format,
            },
            "danmaku": {
                "block_keyword_patterns": ["original-pattern"],
            },
        }
    )


@pytest.mark.parametrize(
    (
        "video_codec",
        "audio_codec",
        "request_video",
        "request_audio",
        "output_format",
        "audio_only_format",
        "audio_save_codec",
        "expected_suffix",
    ),
    [
        ("avc", "flac", True, True, "infer", "infer", "copy", ".mkv"),
        ("avc", "flac", False, True, "infer", "infer", "copy", ".flac"),
        ("avc", "eac3", False, True, "infer", "infer", "copy", ".mkv"),
        ("avc", "mp4a", False, True, "infer", "infer", "copy", ".m4a"),
        ("avc", "mp4a", False, True, "infer", "mp3", "copy", ".mp3"),
        ("avc", "mp4a", True, True, "mov", "infer", "copy", ".mov"),
        ("avc", "mp4a", False, False, "infer", "infer", "copy", ".m4a"),
    ],
)
def test_planner_infers_output_container_without_side_effects(
    tmp_path: Path,
    video_codec: VideoCodec,
    audio_codec: AudioCodec,
    request_video: bool,
    request_audio: bool,
    output_format: str,
    audio_only_format: str,
    audio_save_codec: str,
    expected_suffix: str,
):
    episode = make_episode(videos=[make_video(video_codec)], audios=[make_audio(audio_codec)])
    request = make_request(
        tmp_path,
        video=request_video,
        audio=request_audio,
        video_codec=video_codec,
        audio_codec=audio_codec,
        output_format=output_format,
        audio_only_format=audio_only_format,
        audio_save_codec=audio_save_codec,
    )
    plan = DownloadPlanner().plan(episode, request)

    assert plan.paths.output == tmp_path / f"output/series/episode{expected_suffix}"
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "temporary").exists()


def test_planner_resolves_codecs_hvc1_and_nested_paths(tmp_path: Path):
    episode = make_episode(
        videos=[make_video("hevc")],
        audios=[make_audio("mp4a")],
        path=Path("nested/series/episode"),
    )
    request = make_request(
        tmp_path,
        video=True,
        audio=True,
        video_codec="hevc",
        audio_codec="mp4a",
        video_save_codec="copy",
        audio_save_codec="copy",
        output_format="mp4",
    )

    plan = DownloadPlanner().plan(episode, request)

    assert plan.video is not None
    assert plan.video.index == 0
    assert plan.video_save_codec == "copy"
    assert plan.attach_hvc1_tag is True
    assert plan.audio is not None
    assert plan.audio.index == 0
    assert plan.audio_save_codec == "copy"
    assert plan.paths.video == tmp_path / "temporary/nested/series/episode_video.m4s"
    assert plan.paths.saved_cover == tmp_path / "output/nested/series/episode-poster.jpg"


def test_planner_freezes_inputs_and_hides_signed_urls_from_repr(tmp_path: Path):
    episode = make_episode(videos=[make_video()], audios=[make_audio()])
    request = make_request(tmp_path, video=True, audio=True)

    plan = DownloadPlanner().plan(episode, request)
    episode["videos"][0]["mirrors"].append("https://later.example.test/video")
    episode["audios"][0]["mirrors"].append("https://later.example.test/audio")
    request.danmaku.block_keyword_patterns.append("later-pattern")

    assert plan.video is not None
    assert plan.video.mirrors == ("https://mirror.example.test/video?token=mirror-secret",)
    assert plan.audio is not None
    assert plan.audio.mirrors == ("https://mirror.example.test/audio?token=mirror-secret",)
    assert plan.resources.danmaku.block_keyword_patterns == ("original-pattern",)
    assert "signed.example.test" not in repr(plan)
    assert "mirror.example.test" not in repr(plan)
    with pytest.raises(FrozenInstanceError):
        plan.__setattr__("item", "mutated")


def test_planner_uses_output_directory_when_temporary_directory_is_unset(tmp_path: Path):
    episode = make_episode(audios=[make_audio()])
    request = make_request(
        tmp_path,
        video=False,
        audio=True,
        use_output_as_temporary=True,
    )

    plan = DownloadPlanner().plan(episode, request)

    assert plan.paths.temporary_dir == tmp_path / "output/series"
    assert plan.paths.audio == tmp_path / "output/series/episode_audio.m4s"


def test_planner_precomputes_forced_audio_transcode_notice(tmp_path: Path):
    episode = make_episode(audios=[make_audio()])
    request = make_request(
        tmp_path,
        video=False,
        audio=True,
        audio_only_format="mp3",
        audio_save_codec="copy",
    )

    plan = DownloadPlanner().plan(episode, request)

    assert plan.audio_save_codec == "mp3"
    assert plan.requires_audio_transcode_notice is True
    assert request.stream.audio_save_codec == "copy"
