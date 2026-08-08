from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

import yutto.downloader.executor as executor_module
from yutto.core.execution import ExecutionScope
from yutto.core.request import DownloadRequest
from yutto.core.result import Artifact, ArtifactKind, ItemResult, ItemSkipReason, ItemState, ResolvedItem
from yutto.downloader.downloader import process_download
from yutto.downloader.media_muxer import MediaMuxer
from yutto.exceptions import PostprocessingError
from yutto.types import AId, CId
from yutto.utils.danmaku import write_danmaku
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from yutto.downloader.planner import DownloadPlan
    from yutto.media.codec import AudioCodec
    from yutto.types import AudioUrlMeta, EpisodeData
    from yutto.utils.danmaku import DanmakuData, DanmakuOptions

pytestmark = pytest.mark.processor


def make_request(
    tmp_path: Path,
    *,
    video: bool = False,
    audio: bool = False,
    save_cover: bool = True,
) -> DownloadRequest:
    return DownloadRequest.model_validate(
        {
            "source": {"url": "BV1test"},
            "resources": {
                "video": video,
                "audio": audio,
                "chapter_info": False,
                "save_cover": save_cover,
            },
            "stream": {
                "video_quality": 80,
                "video_download_codec": "avc",
                "video_save_codec": "copy",
                "audio_quality": 30280,
                "audio_download_codec": "mp4a",
                "audio_save_codec": "copy",
            },
            "output": {
                "directory": tmp_path / "output",
                "temporary_directory": tmp_path / "temporary",
            },
        }
    )


def make_resource_only_episode() -> EpisodeData:
    planned_path = Path("series/episode")
    return {
        "info": {
            "listing": ResolvedItem(
                avid=AId("1"),
                cid=CId("1"),
                url="https://www.bilibili.com/video/av1?p=1",
                name="episode",
                title="episode",
                cover_url="",
                planned_path=planned_path,
            ),
            "path": planned_path,
        },
        "videos": [],
        "audios": [],
        "subtitles": [
            {
                "lang": "zh-CN",
                "lines": [{"content": "测试", "from": 0, "to": 1}],
            }
        ],
        "metadata": {
            "title": "测试",
            "show_title": "测试",
            "plot": "",
            "thumb": "",
            "premiered": 0,
            "dateadded": 0,
            "actor": [],
            "genre": [],
            "tag": [],
            "source": "",
            "original_filename": "episode",
            "website": "",
            "chapter_info_data": [],
        },
        "danmaku": {"source_type": "xml", "save_type": "xml", "data": ["<i />"]},
        "cover_data": b"cover",
        "chapter_info_data": [],
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


def make_media_episode() -> EpisodeData:
    episode = make_resource_only_episode()
    episode["audios"] = [make_audio()]
    episode["chapter_info_data"] = [{"start": 0, "end": 1, "content": "chapter"}]
    return episode


@pytest.mark.parametrize("cancelled", [False, True], ids=["failure", "cancellation"])
@as_sync
async def test_interrupted_mux_keeps_resume_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cancelled: bool,
):
    started = asyncio.Event()

    class InterruptedFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            if cancelled:
                started.set()
                await asyncio.Event().wait()
            return subprocess.CompletedProcess(args, 1, b"", b"ffmpeg failed")

    async def write_audio_fragment(_scope: ExecutionScope, plan: DownloadPlan) -> None:
        plan.paths.audio.write_bytes(b"resumable audio")

    muxer = MediaMuxer(InterruptedFFmpeg())
    monkeypatch.setattr(executor_module, "download_video_and_audio", write_audio_fragment)
    monkeypatch.setattr(executor_module, "MediaMuxer", lambda: muxer)
    execution = asyncio.create_task(
        process_download(
            ExecutionScope(cast("Any", object())),
            make_media_episode(),
            make_request(tmp_path, audio=True),
        )
    )
    if cancelled:
        await started.wait()
        execution.cancel()
        error = asyncio.CancelledError
    else:
        error = PostprocessingError

    with pytest.raises(error):
        await execution

    output_dir = tmp_path / "output/series"
    temporary_dir = tmp_path / "temporary/series"
    assert (output_dir / "episode.zh-CN.srt").exists()
    assert (temporary_dir / "episode_audio.m4s").read_bytes() == b"resumable audio"
    assert (temporary_dir / "episode_cover.jpg").exists()
    assert (temporary_dir / "episode_chapter_info.ini").exists()
    assert not (output_dir / "episode.m4a").exists()


@as_sync
async def test_resource_only_download_returns_final_artifacts_without_temporary_files(tmp_path: Path):
    result = await process_download(
        ExecutionScope(cast("Any", object())),
        make_resource_only_episode(),
        make_request(tmp_path),
    )

    output_dir = tmp_path / "output/series"
    assert result == ItemResult(
        state=ItemState.DONE,
        output_path=output_dir / "episode.m4a",
        artifacts=(
            Artifact(kind=ArtifactKind.SUBTITLE, path=output_dir / "episode.zh-CN.srt"),
            Artifact(kind=ArtifactKind.DANMAKU, path=output_dir / "episode.xml"),
            Artifact(kind=ArtifactKind.METADATA, path=output_dir / "episode.nfo"),
            Artifact(kind=ArtifactKind.COVER, path=output_dir / "episode-poster.jpg"),
        ),
    )
    assert all(artifact.path.exists() for artifact in result.artifacts)
    assert not (tmp_path / "temporary/series/episode_cover.jpg").exists()


@as_sync
async def test_existing_media_returns_artifacts_and_cleans_temporary_resources(tmp_path: Path):
    episode = make_media_episode()
    episode["metadata"] = None
    episode["danmaku"] = {"source_type": None, "save_type": None, "data": []}
    output_path = tmp_path / "output/series/episode.m4a"
    subtitle_path = tmp_path / "output/series/episode.zh-CN.srt"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"existing")
    subtitle_path.write_text("stale subtitle")

    result = await process_download(
        ExecutionScope(cast("Any", object())),
        episode,
        make_request(tmp_path, audio=True),
    )

    assert result == ItemResult(
        state=ItemState.SKIPPED,
        output_path=output_path,
        skip_reason=ItemSkipReason.ALREADY_EXISTS,
        artifacts=(
            Artifact(kind=ArtifactKind.SUBTITLE, path=subtitle_path),
            Artifact(kind=ArtifactKind.COVER, path=tmp_path / "output/series/episode-poster.jpg"),
            Artifact(kind=ArtifactKind.MEDIA, path=output_path),
        ),
    )
    assert subtitle_path.read_text() != "stale subtitle"
    assert not (tmp_path / "temporary/series/episode_cover.jpg").exists()
    assert not (tmp_path / "temporary/series/episode_chapter_info.ini").exists()


@as_sync
async def test_missing_requested_audio_does_not_clean_uncreated_video_file(tmp_path: Path):
    episode = make_resource_only_episode()
    episode["videos"] = [
        {
            "url": "https://example.test/video",
            "mirrors": [],
            "codec": "avc",
            "width": 1920,
            "height": 1080,
            "quality": 80,
        }
    ]
    episode["subtitles"] = []
    episode["metadata"] = None
    episode["danmaku"] = {"source_type": None, "save_type": None, "data": []}
    episode["cover_data"] = None

    result = await process_download(
        ExecutionScope(cast("Any", object())),
        episode,
        make_request(tmp_path, audio=True, save_cover=False),
    )

    assert result == ItemResult(
        state=ItemState.SKIPPED,
        output_path=tmp_path / "output/series/episode.m4a",
        skip_reason=ItemSkipReason.NO_MEDIA_STREAM,
    )


def test_multi_part_protobuf_danmaku_returns_every_output_path(tmp_path: Path):
    danmaku = cast(
        "DanmakuData",
        {"source_type": "protobuf", "save_type": "protobuf", "data": [b"first", b"second"]},
    )

    paths = write_danmaku(danmaku, tmp_path / "video.mp4", 1080, 1920, cast("DanmakuOptions", {}))

    assert paths == [tmp_path / "video_00.pb", tmp_path / "video_01.pb"]
    assert [path.read_bytes() for path in paths] == [b"first", b"second"]
