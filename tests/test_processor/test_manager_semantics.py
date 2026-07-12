from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success

import yutto.download_manager as download_manager_module
from yutto.core.request import DownloadRequest
from yutto.download_manager import (
    DownloadManager,
    DownloadTask,
    ensure_output_path_is_scoped,
    ensure_unique_path,
    show_batch_episode_title,
)
from yutto.downloader.downloader import DownloadState
from yutto.exceptions import WrongArgumentError
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import Filter
from yutto.utils.functional import as_sync
from yutto.utils.time import TIME_FULL_FMT

if TYPE_CHECKING:
    import httpx

    from yutto.types import DownloaderOptions, EpisodeData, ExtractorOptions

pytestmark = pytest.mark.processor


def make_episode(path: str, display_group: str | None = None) -> EpisodeData:
    return {
        "videos": [],
        "audios": [],
        "subtitles": [],
        "metadata": None,
        "danmaku": {"source_type": None, "save_type": None, "data": []},
        "cover_data": None,
        "chapter_info_data": [],
        "path": Path(path),
        "display_group": display_group,
    }


def make_request(tmp_dir: Path | None) -> DownloadRequest:
    return DownloadRequest.model_validate(
        {
            "source": {"url": "BV1baseline"},
            "scope": {"batch": False, "with_section": True},
            "selection": {
                "episodes": "2,4",
                "start_time": "2024-01-02 03:04:05",
                "end_time": "2025-06-07",
            },
            "resources": {
                "video": True,
                "audio": False,
                "danmaku": True,
                "subtitle": False,
                "metadata": True,
                "cover": True,
                "chapter_info": True,
                "save_cover": True,
                "ai_translation_language": "ja",
            },
            "stream": {
                "video_quality": 116,
                "video_download_codec": "hevc",
                "video_save_codec": "av1",
                "video_download_codec_priority": ["av1", "hevc"],
                "audio_quality": 30280,
                "audio_download_codec": "eac3",
                "audio_save_codec": "flac",
            },
            "output": {
                "directory": Path("downloads"),
                "temporary_directory": tmp_dir,
                "format": "mkv",
                "audio_only_format": "flac",
                "overwrite": True,
                "subpath_template": "{title}/{name}",
                "metadata_format_premiered": "%Y",
            },
            "network": {
                "block_size_bytes": 1_310_720,
                "download_workers": 13,
                "banned_mirrors_pattern": "example\\.com",
            },
            "danmaku": {
                "format": "protobuf",
                "font_size": 48,
                "font": "Test Font",
                "opacity": 0.6,
                "display_region_ratio": 0.75,
                "speed": 1.25,
                "block_top": True,
                "block_bottom": True,
                "block_scroll": True,
                "block_reverse": True,
                "block_special": True,
                "block_colorful": True,
                "block_keyword_patterns": ["spam", "eggs"],
            },
        }
    )


@pytest.mark.processor
@pytest.mark.parametrize("tmp_dir", [None, Path("temporary")])
@as_sync
async def test_process_task_preserves_extractor_and_downloader_option_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_dir: Path | None
):
    monkeypatch.setattr(Filter, "batch_filter_start_time", Filter.batch_filter_start_time)
    monkeypatch.setattr(Filter, "batch_filter_end_time", Filter.batch_filter_end_time)
    captured_extractor_options: dict[str, Any] = {}
    captured_downloader_options: dict[str, Any] = {}
    validation_requirements: list[dict[str, bool]] = []
    episode = make_episode("series/episode")

    class FakeExtractor:
        def resolve_shortcut(self, url: str) -> tuple[bool, str]:
            return True, f"https://example.com/{url}"

        def match(self, url: str) -> bool:
            return url == "https://example.com/BV1baseline"

        async def __call__(
            self,
            ctx: FetcherContext,
            client: httpx.AsyncClient,
            options: ExtractorOptions,
        ):
            captured_extractor_options.update(options)

            async def resolve_episode() -> EpisodeData:
                return episode

            return [resolve_episode()]

    async def fake_validate_user_info(ctx: FetcherContext, requirements: dict[str, bool]) -> bool:
        validation_requirements.append(requirements)
        return True

    async def fake_get_redirected_url(ctx: FetcherContext, client: httpx.AsyncClient, url: str):
        return Success(url)

    async def fake_process_download(
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        episode_data: EpisodeData,
        options: DownloaderOptions,
    ) -> DownloadState:
        assert episode_data is episode
        captured_downloader_options.update(options)
        return DownloadState.DONE

    def fake_block_options(**options: Any) -> dict[str, Any]:
        return options

    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", FakeExtractor)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)
    monkeypatch.setattr(download_manager_module, "process_download", fake_process_download)
    monkeypatch.setattr(download_manager_module, "BlockOptions", fake_block_options)
    monkeypatch.setattr(Logger, "new_line", lambda: None)

    manager = DownloadManager()
    client = cast("httpx.AsyncClient", object())
    await manager.process_task(client, FetcherContext(), DownloadTask(request=make_request(tmp_dir)))

    assert validation_requirements == [
        {"is_login": False, "vip_status": False},
        {"is_login": False, "vip_status": False},
    ]
    assert Filter.batch_filter_start_time == datetime(2024, 1, 2, 3, 4, 5)
    assert Filter.batch_filter_end_time == datetime(2025, 6, 7)
    assert captured_extractor_options == {
        "episodes": "2,4",
        "with_section": True,
        "require_video": True,
        "require_audio": False,
        "require_danmaku": True,
        "require_subtitle": False,
        "require_metadata": True,
        "require_cover": True,
        "require_chapter_info": True,
        "danmaku_format": "protobuf",
        "subpath_template": "{title}/{name}",
        "ai_translation_language": "ja",
    }
    assert captured_downloader_options == {
        "output_dir": Path("downloads"),
        "tmp_dir": tmp_dir or Path("downloads"),
        "require_video": True,
        "require_chapter_info": True,
        "video_quality": 116,
        "video_download_codec": "hevc",
        "video_save_codec": "av1",
        "video_download_codec_priority": ["av1", "hevc"],
        "require_audio": False,
        "audio_quality": 30280,
        "audio_download_codec": "eac3",
        "audio_save_codec": "flac",
        "output_format": "mkv",
        "output_format_audio_only": "flac",
        "overwrite": True,
        "block_size": 1_310_720,
        "num_workers": 13,
        "save_cover": True,
        "metadata_format": {"premiered": "%Y", "dateadded": TIME_FULL_FMT},
        "banned_mirrors_pattern": "example\\.com",
        "danmaku_options": {
            "font_size": 48,
            "font": "Test Font",
            "opacity": 0.6,
            "display_region_ratio": 0.75,
            "speed": 1.25,
            "block_options": {
                "block_top": True,
                "block_bottom": True,
                "block_scroll": True,
                "block_reverse": True,
                "block_special": True,
                "block_colorful": True,
                "block_keyword_patterns": ["spam", "eggs"],
            },
        },
    }


@pytest.mark.processor
def test_ensure_unique_path_updates_episode_and_only_warns_on_rename(monkeypatch: pytest.MonkeyPatch):
    warnings: list[str] = []
    resolved_paths: list[str] = []

    def resolve_unique_path(path: str) -> str:
        resolved_paths.append(path)
        return "group/video (1).mp4"

    monkeypatch.setattr(Logger, "warning", lambda message: warnings.append(str(message)))

    renamed_episode = make_episode("group/video.mp4")
    result = ensure_unique_path(renamed_episode, resolve_unique_path)

    assert result is renamed_episode
    assert result["path"] == Path("group/video (1).mp4")
    assert resolved_paths == ["group/video.mp4"]
    assert warnings == ["文件名重复，已重命名为 video (1).mp4"]

    unchanged_episode = make_episode("group/another.mp4")
    ensure_unique_path(unchanged_episode, lambda path: path)
    assert warnings == ["文件名重复，已重命名为 video (1).mp4"]


@pytest.mark.processor
def test_show_batch_episode_title_preserves_order_and_group_state(monkeypatch: pytest.MonkeyPatch):
    output: list[tuple[str, str]] = []

    def capture_output(message: Any, badge: Badge, *args: Any, **kwargs: Any):
        output.append((str(message), badge.text))

    monkeypatch.setattr(Logger, "custom", capture_output)

    current_group: str | None = None
    group_states: list[str | None] = []
    episodes = [
        make_episode("投稿 A/P1", "投稿 A"),
        make_episode("投稿 A/P2", "投稿 A"),
        make_episode("单集"),
        make_episode("投稿 B/P1", "投稿 B"),
    ]
    for index, episode in enumerate(episodes, start=1):
        current_group = show_batch_episode_title(episode, index, len(episodes), current_group)
        group_states.append(current_group)

    assert group_states == ["投稿 A", "投稿 A", None, "投稿 B"]
    assert output == [
        ("投稿 A", "列表"),
        ("  P1", "[1/4]"),
        ("  P2", "[2/4]"),
        ("单集", "[3/4]"),
        ("投稿 B", "列表"),
        ("  P1", "[4/4]"),
    ]


@pytest.mark.processor
def test_server_output_boundary_checks_final_rendered_path(tmp_path: Path):
    output_root = tmp_path / "output"
    temporary_root = tmp_path / "temporary"
    outside = tmp_path / "outside"
    output_root.mkdir()
    temporary_root.mkdir()
    outside.mkdir()

    ensure_output_path_is_scoped(Path("series/episode"), output_root, temporary_root)

    with pytest.raises(WrongArgumentError, match="超出了"):
        ensure_output_path_is_scoped(Path("../outside/episode"), output_root, temporary_root)
    with pytest.raises(WrongArgumentError, match="超出了"):
        ensure_output_path_is_scoped(Path("/outside/episode"), output_root, temporary_root)

    (output_root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WrongArgumentError, match="超出了"):
        ensure_output_path_is_scoped(Path("linked/episode"), output_root, temporary_root)
