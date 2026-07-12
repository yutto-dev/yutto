from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from yutto.core.result import Artifact, ArtifactKind, ItemResult, ItemSkipReason, ItemState
from yutto.downloader.downloader import process_download
from yutto.utils.danmaku import write_danmaku
from yutto.utils.fetcher import FetcherContext
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx

    from yutto.types import DownloaderOptions, EpisodeData
    from yutto.utils.danmaku import DanmakuData, DanmakuOptions

pytestmark = pytest.mark.processor


def make_options(tmp_path: Path) -> DownloaderOptions:
    return {
        "output_dir": tmp_path / "output",
        "tmp_dir": tmp_path / "temporary",
        "require_video": False,
        "require_chapter_info": False,
        "save_cover": True,
        "video_quality": 80,
        "video_download_codec": "avc",
        "video_save_codec": "copy",
        "video_download_codec_priority": None,
        "require_audio": False,
        "audio_quality": 30280,
        "audio_download_codec": "mp4a",
        "audio_save_codec": "copy",
        "output_format": "infer",
        "output_format_audio_only": "infer",
        "overwrite": False,
        "block_size": 512 * 1024,
        "num_workers": 1,
        "metadata_format": {},
        "banned_mirrors_pattern": None,
        "danmaku_options": cast("DanmakuOptions", {}),
    }


def make_resource_only_episode() -> EpisodeData:
    return {
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
        "path": Path("series/episode"),
        "display_group": None,
    }


@as_sync
async def test_resource_only_download_returns_final_artifacts_without_temporary_files(tmp_path: Path):
    result = await process_download(
        FetcherContext(),
        cast("httpx.AsyncClient", object()),
        make_resource_only_episode(),
        make_options(tmp_path),
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
async def test_existing_media_is_reported_and_temporary_resources_are_cleaned(tmp_path: Path):
    options = make_options(tmp_path)
    options["require_audio"] = True
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
        FetcherContext(),
        cast("httpx.AsyncClient", object()),
        episode,
        options,
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
    options = make_options(tmp_path)
    options["require_audio"] = True
    options["save_cover"] = False
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
        FetcherContext(),
        cast("httpx.AsyncClient", object()),
        episode,
        options,
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

    assert paths == (tmp_path / "video_00.pb", tmp_path / "video_01.pb")
    assert [path.read_bytes() for path in paths] == [b"first", b"second"]
