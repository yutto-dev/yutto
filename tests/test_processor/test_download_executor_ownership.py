from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import yutto.downloader.executor as executor_module
from tests.test_processor.test_download_result import (
    make_request,
    make_resource_only_episode,
)
from yutto.core.execution import ExecutionScope
from yutto.core.result import ArtifactKind, ItemSkipReason, ItemState
from yutto.downloader.downloader import process_download
from yutto.downloader.media_muxer import MediaMuxer
from yutto.exceptions import PostprocessingError
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx

    from yutto.downloader.planner import DownloadPlan

pytestmark = pytest.mark.processor


def make_media_episode():
    episode = make_resource_only_episode()
    episode["audios"] = [
        {
            "url": "https://example.test/audio",
            "mirrors": [],
            "codec": "mp4a",
            "width": 0,
            "height": 0,
            "quality": 30280,
        }
    ]
    episode["chapter_info_data"] = [{"start": 0, "end": 1, "content": "chapter"}]
    return episode


async def write_audio_fragment(_scope: ExecutionScope, plan: DownloadPlan) -> None:
    plan.paths.audio.write_bytes(b"resumable audio")


@as_sync
async def test_mux_failure_keeps_resume_inputs_and_sidecars_but_removes_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    class FailingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            return subprocess.CompletedProcess(args, 1, b"", b"ffmpeg failed")

    muxer = MediaMuxer(FailingFFmpeg())
    monkeypatch.setattr(executor_module, "download_video_and_audio", write_audio_fragment)
    monkeypatch.setattr(executor_module, "MediaMuxer", lambda: muxer)
    with pytest.raises(PostprocessingError, match="ffmpeg failed"):
        await process_download(
            ExecutionScope(cast("httpx.AsyncClient", object())),
            make_media_episode(),
            make_request(tmp_path, audio=True),
        )

    output_dir = tmp_path / "output/series"
    temporary_dir = tmp_path / "temporary/series"
    assert (output_dir / "episode.zh-CN.srt").exists()
    assert (output_dir / "episode.xml").exists()
    assert (output_dir / "episode.nfo").exists()
    assert (output_dir / "episode-poster.jpg").exists()
    assert (temporary_dir / "episode_audio.m4s").read_bytes() == b"resumable audio"
    assert (temporary_dir / "episode_cover.jpg").exists()
    assert (temporary_dir / "episode_chapter_info.ini").exists()
    assert not (output_dir / "episode.m4a").exists()


@as_sync
async def test_mux_cancellation_keeps_resume_inputs_and_sidecars_but_removes_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    started = asyncio.Event()

    class BlockingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    muxer = MediaMuxer(BlockingFFmpeg())
    monkeypatch.setattr(executor_module, "download_video_and_audio", write_audio_fragment)
    monkeypatch.setattr(executor_module, "MediaMuxer", lambda: muxer)
    task = asyncio.create_task(
        process_download(
            ExecutionScope(cast("httpx.AsyncClient", object())),
            make_media_episode(),
            make_request(tmp_path, audio=True),
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    output_dir = tmp_path / "output/series"
    temporary_dir = tmp_path / "temporary/series"
    assert (output_dir / "episode.zh-CN.srt").exists()
    assert (output_dir / "episode-poster.jpg").exists()
    assert (temporary_dir / "episode_audio.m4s").exists()
    assert (temporary_dir / "episode_cover.jpg").exists()
    assert (temporary_dir / "episode_chapter_info.ini").exists()
    assert not (output_dir / "episode.m4a").exists()


@as_sync
async def test_existing_media_refreshes_sidecars_without_starting_media_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    async def unexpected_download(_scope: ExecutionScope, _plan: DownloadPlan) -> None:
        raise AssertionError("existing media must skip transfer")

    class UnexpectedMuxer:
        def __init__(self):
            raise AssertionError("existing media must skip muxing")

    monkeypatch.setattr(executor_module, "download_video_and_audio", unexpected_download)
    monkeypatch.setattr(executor_module, "MediaMuxer", UnexpectedMuxer)
    episode = make_media_episode()
    output_dir = tmp_path / "output/series"
    output_dir.mkdir(parents=True)
    output_path = output_dir / "episode.m4a"
    subtitle_path = output_dir / "episode.zh-CN.srt"
    output_path.write_bytes(b"existing media")
    subtitle_path.write_text("stale subtitle")
    result = await process_download(
        ExecutionScope(cast("httpx.AsyncClient", object())),
        episode,
        make_request(tmp_path, audio=True),
    )

    assert result.state is ItemState.SKIPPED
    assert result.skip_reason is ItemSkipReason.ALREADY_EXISTS
    assert [artifact.kind for artifact in result.artifacts][-1] is ArtifactKind.MEDIA
    assert output_path.read_bytes() == b"existing media"
    assert subtitle_path.read_text() != "stale subtitle"
    assert not (tmp_path / "temporary/series/episode_cover.jpg").exists()
    assert not (tmp_path / "temporary/series/episode_chapter_info.ini").exists()


@as_sync
async def test_overwrite_cancellation_does_not_restore_old_media_and_restarts_fragment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    async def cancel_download(_scope: ExecutionScope, plan: DownloadPlan) -> None:
        assert not plan.paths.output.exists()
        async with await AsyncFileBuffer.open(plan.paths.audio, overwrite=plan.overwrite) as buffer:
            assert buffer.written_size == 0
            await buffer.write(b"new partial audio", 0)
            raise asyncio.CancelledError

    monkeypatch.setattr(executor_module, "download_video_and_audio", cancel_download)
    episode = make_media_episode()
    request = make_request(tmp_path, audio=True)
    request.output.overwrite = True
    output_path = tmp_path / "output/series/episode.m4a"
    fragment_path = tmp_path / "temporary/series/episode_audio.m4s"
    output_path.parent.mkdir(parents=True)
    fragment_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"old media")
    fragment_path.write_bytes(b"old fragment")

    with pytest.raises(asyncio.CancelledError):
        await process_download(
            ExecutionScope(cast("httpx.AsyncClient", object())),
            episode,
            request,
        )

    assert not output_path.exists()
    assert fragment_path.read_bytes() == b"new partial audio"
    assert (tmp_path / "temporary/series/episode_cover.jpg").exists()
    assert (tmp_path / "temporary/series/episode_chapter_info.ini").exists()
