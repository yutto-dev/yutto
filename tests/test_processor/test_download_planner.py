from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pytest

from tests.test_processor.test_download_result import make_audio, make_request, make_resource_only_episode
from yutto.core.events import DownloadMediaSelected, SelectedAudioStream, SelectedVideoStream
from yutto.core.operation import bind_download_event_sink
from yutto.downloader.executor import emit_streams_selected
from yutto.downloader.planner import DownloadPlan, DownloadPlanner

if TYPE_CHECKING:
    from yutto.core.request import DownloadRequest
    from yutto.media.codec import AudioCodec, VideoCodec
    from yutto.types import EpisodeData, VideoUrlMeta

pytestmark = pytest.mark.processor

OutputFormat = Literal["infer", "mp4", "mkv", "mov"]
AudioOnlyFormat = Literal["infer", "m4a", "aac", "mp3", "flac", "mp4", "mkv", "mov"]


def make_video(codec: VideoCodec = "avc") -> VideoUrlMeta:
    return {
        "url": "https://signed.example.test/video?token=video-secret",
        "mirrors": ["https://mirror.example.test/video?token=mirror-secret"],
        "codec": codec,
        "width": 1920,
        "height": 1080,
        "quality": 80,
    }


def make_plan(
    tmp_path: Path,
    *,
    video_codec: VideoCodec | None = None,
    audio_codec: AudioCodec | None = None,
    output_format: OutputFormat = "infer",
    audio_only_format: AudioOnlyFormat = "infer",
    path: Path = Path("series/episode"),
    use_output_as_temporary: bool = False,
) -> tuple[EpisodeData, DownloadRequest, DownloadPlan]:
    episode = make_resource_only_episode()
    episode["info"]["path"] = path
    episode["videos"] = [make_video(video_codec)] if video_codec is not None else []
    episode["audios"] = [make_audio(audio_codec)] if audio_codec is not None else []
    request = make_request(
        tmp_path,
        video=video_codec is not None,
        audio=audio_codec is not None,
    )
    if video_codec is not None:
        request.stream.video_download_codec = video_codec
    if audio_codec is not None:
        request.stream.audio_download_codec = audio_codec
    request.output.format = output_format
    request.output.audio_only_format = audio_only_format
    if use_output_as_temporary:
        request.output.temporary_directory = None
    request.danmaku.block_keyword_patterns = ["original-pattern"]
    return episode, request, DownloadPlanner().plan(episode, request)


@pytest.mark.parametrize(
    ("video_codec", "audio_codec", "output_format", "audio_only_format", "suffix"),
    [
        ("avc", "flac", "infer", "infer", ".mkv"),
        (None, "flac", "infer", "infer", ".flac"),
        (None, "eac3", "infer", "infer", ".mkv"),
        (None, "mp4a", "infer", "mp3", ".mp3"),
        ("avc", "mp4a", "mov", "infer", ".mov"),
    ],
)
def test_planner_resolves_output_without_io(
    tmp_path: Path,
    video_codec: VideoCodec | None,
    audio_codec: AudioCodec | None,
    output_format: OutputFormat,
    audio_only_format: AudioOnlyFormat,
    suffix: str,
):
    _, _, plan = make_plan(
        tmp_path,
        video_codec=video_codec,
        audio_codec=audio_codec,
        output_format=output_format,
        audio_only_format=audio_only_format,
    )

    assert plan.paths.output == tmp_path / f"output/series/episode{suffix}"
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "temporary").exists()


def test_planner_snapshots_inputs_without_exposing_signed_urls(tmp_path: Path):
    episode, request, plan = make_plan(tmp_path, video_codec="avc", audio_codec="mp4a")
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


def test_stream_selection_event_projects_only_the_final_safe_media_values(tmp_path: Path):
    episode, _, plan = make_plan(tmp_path, video_codec="av1", audio_codec="mp4a")
    events = []

    class Sink:
        def emit(self, event) -> None:
            events.append(event)

    with bind_download_event_sink(Sink()):
        emit_streams_selected(episode, plan)

    assert events == [
        DownloadMediaSelected(
            item="episode",
            video=SelectedVideoStream(
                codec="av1",
                quality=80,
                width=1920,
                height=1080,
                save_codec="copy",
            ),
            audio=SelectedAudioStream(codec="mp4a", quality=30280, save_codec="copy"),
        )
    ]
    assert "signed.example.test" not in repr(events)
    assert "mirror.example.test" not in repr(events)


def test_planner_resolves_nested_temporary_paths_and_forced_transcode(tmp_path: Path):
    _, request, plan = make_plan(
        tmp_path,
        audio_codec="mp4a",
        audio_only_format="mp3",
        path=Path("nested/series/episode"),
        use_output_as_temporary=True,
    )

    assert plan.paths.temporary_dir == tmp_path / "output/nested/series"
    assert plan.paths.audio == tmp_path / "output/nested/series/episode_audio.m4s"
    assert plan.paths.saved_cover == tmp_path / "output/nested/series/episode-poster.jpg"
    assert plan.audio_save_codec == "mp3"
    assert plan.requires_audio_transcode_notice is True
    assert request.stream.audio_save_codec == "copy"
