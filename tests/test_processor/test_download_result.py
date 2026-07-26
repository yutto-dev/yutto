from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from returns.result import Success

import yutto.downloader.transfer as transfer_module
from yutto.core.execution import ExecutionScope
from yutto.core.request import DownloadRequest
from yutto.core.result import Artifact, ArtifactKind, ItemResult, ItemSkipReason, ItemState, ResolvedItem
from yutto.downloader.downloader import process_download
from yutto.downloader.planner import DownloadPlanner
from yutto.types import AId, AudioUrlMeta, CId
from yutto.utils.danmaku import write_danmaku
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx

    from yutto.types import EpisodeData
    from yutto.utils.danmaku import DanmakuData, DanmakuOptions
    from yutto.utils.file_buffer import AsyncFileBuffer

pytestmark = pytest.mark.processor


def make_request(
    tmp_path: Path,
    *,
    audio: bool = False,
    save_cover: bool = True,
) -> DownloadRequest:
    return DownloadRequest.model_validate(
        {
            "source": {"url": "BV1test"},
            "resources": {
                "video": False,
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


@as_sync
async def test_download_cancellation_closes_buffer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    download_started = asyncio.Event()
    download_cancelled = asyncio.Event()
    buffer_closed = asyncio.Event()

    async def get_size(_scope: ExecutionScope, _url: str) -> Success[int]:
        return Success(1)

    async def download_file(*_args: object, **_kwargs: object) -> None:
        download_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            download_cancelled.set()

    async def show_progress(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    original_close = transfer_module.AsyncFileBuffer.close

    async def close_buffer(buffer: AsyncFileBuffer) -> None:
        await original_close(buffer)
        buffer_closed.set()

    monkeypatch.setattr(transfer_module.Fetcher, "get_size", get_size)
    monkeypatch.setattr(transfer_module.Fetcher, "download_file_with_offset", download_file)
    monkeypatch.setattr(transfer_module, "show_progress", show_progress)
    monkeypatch.setattr(transfer_module.AsyncFileBuffer, "close", close_buffer)

    audio: AudioUrlMeta = {
        "url": "https://example.test/audio",
        "mirrors": [],
        "codec": "mp4a",
        "width": 0,
        "height": 0,
        "quality": 30280,
    }
    episode = make_resource_only_episode()
    episode["audios"] = [audio]
    plan = DownloadPlanner().plan(episode, make_request(tmp_path, audio=True))
    plan.paths.temporary_dir.mkdir(parents=True)
    task = asyncio.create_task(
        transfer_module.download_video_and_audio(
            ExecutionScope(cast("httpx.AsyncClient", object())),
            plan,
        )
    )
    await download_started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert download_cancelled.is_set()
    assert buffer_closed.is_set()


@as_sync
async def test_resource_only_download_returns_final_artifacts_without_temporary_files(tmp_path: Path):
    result = await process_download(
        ExecutionScope(cast("httpx.AsyncClient", object())),
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
    episode = make_resource_only_episode()
    episode["subtitles"] = []
    episode["metadata"] = None
    episode["danmaku"] = {"source_type": None, "save_type": None, "data": []}
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
    output_path = tmp_path / "output/series/episode.m4a"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"existing")

    result = await process_download(
        ExecutionScope(cast("httpx.AsyncClient", object())),
        episode,
        make_request(tmp_path, audio=True),
    )

    assert result == ItemResult(
        state=ItemState.SKIPPED,
        output_path=output_path,
        skip_reason=ItemSkipReason.ALREADY_EXISTS,
        artifacts=(
            Artifact(kind=ArtifactKind.COVER, path=tmp_path / "output/series/episode-poster.jpg"),
            Artifact(kind=ArtifactKind.MEDIA, path=output_path),
        ),
    )
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
        ExecutionScope(cast("httpx.AsyncClient", object())),
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
