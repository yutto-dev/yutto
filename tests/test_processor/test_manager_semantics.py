from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success

import yutto.download_manager as download_manager_module
from yutto.core.execution import ExecutionScope, RequestExecutionScopeFactory
from yutto.core.operation import ReportLevel, bind_download_report_sink
from yutto.core.request import DownloadRequest
from yutto.core.result import DownloadResult, ItemResult, ItemState, ResolvedItem
from yutto.download_manager import (
    DownloadManager,
    ensure_output_path_is_scoped,
    ensure_unique_path,
    show_batch_episode_title,
)
from yutto.exceptions import NotLoginError, WrongArgumentError
from yutto.extractor.outcome import ResolveOutcome
from yutto.types import AId, CId, ResolvableEpisode
from yutto.utils.fetcher import Fetcher
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import httpx

    from yutto.auth import AuthInfo
    from yutto.extractor._abc import ExtractorResolveOutcome
    from yutto.types import EpisodeData, ExtractorOptions

pytestmark = pytest.mark.processor


def make_episode(path: str, display_group: str | None = None) -> EpisodeData:
    planned_path = Path(path)
    return {
        "info": {
            "listing": ResolvedItem(
                avid=AId("1"),
                cid=CId("1"),
                url="https://www.bilibili.com/video/av1?p=1",
                name=planned_path.name,
                title=planned_path.name,
                cover_url="",
                planned_path=planned_path,
                display_group=display_group,
            ),
            "path": planned_path,
        },
        "videos": [],
        "audios": [],
        "subtitles": [],
        "metadata": None,
        "danmaku": {"source_type": None, "save_type": None, "data": []},
        "cover_data": None,
        "chapter_info_data": [],
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
async def test_process_request_preserves_extractor_mapping_and_passes_download_request_directly(
    monkeypatch: pytest.MonkeyPatch, tmp_dir: Path | None
):
    captured_extractor_options: dict[str, Any] = {}
    captured_download_request: DownloadRequest | None = None
    validation_requirements: list[dict[str, bool]] = []
    episode = make_episode("series/episode")

    class FakeExtractor:
        def resolve_shortcut(self, url: str) -> tuple[bool, str]:
            return True, f"https://example.com/{url}"

        def match(self, url: str) -> bool:
            return url == "https://example.com/BV1baseline"

        async def __call__(
            self,
            scope: ExecutionScope,
            options: ExtractorOptions,
        ) -> ExtractorResolveOutcome:
            captured_extractor_options.update(options)

            async def resolve_episode() -> EpisodeData | None:
                return episode

            return ResolveOutcome(items=(ResolvableEpisode(info=episode["info"], resolve_data=resolve_episode),))

    async def fake_validate_user_info(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        validation_requirements.append(requirements)
        return True

    async def fake_get_redirected_url(scope: ExecutionScope, url: str):
        return Success(url)

    async def fake_process_download(
        scope: ExecutionScope,
        episode_data: EpisodeData,
        request: DownloadRequest,
    ) -> ItemResult:
        nonlocal captured_download_request
        assert episode_data is episode
        captured_download_request = request
        return ItemResult(state=ItemState.DONE, output_path=Path("downloads/series/episode.mkv"))

    monkeypatch.setattr(download_manager_module, "UgcVideoExtractor", FakeExtractor)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", fake_get_redirected_url)
    monkeypatch.setattr(download_manager_module, "process_download", fake_process_download)

    manager = DownloadManager()
    client = cast("httpx.AsyncClient", object())
    request = make_request(tmp_dir)
    result = await manager.process_request(ExecutionScope(client), request)

    assert validation_requirements == [
        {"is_login": False, "vip_status": False},
        {"is_login": False, "vip_status": False},
    ]
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
        "publication_time_filter": PublicationTimeFilter(
            start_time=datetime(2024, 1, 2, 3, 4, 5),
            end_time=datetime(2025, 6, 7),
        ),
    }
    assert captured_download_request is request
    assert result == (ItemResult(state=ItemState.DONE, output_path=Path("downloads/series/episode.mkv")),)


@as_sync
async def test_process_request_does_not_create_unreached_episode_coroutines(monkeypatch: pytest.MonkeyPatch):
    first_episode = make_episode("series/first")
    second_episode = make_episode("series/second")
    created_coroutines: list[str] = []

    def make_resolver(name: str, episode: EpisodeData):
        def resolve_data():
            created_coroutines.append(name)

            async def resolve_episode() -> EpisodeData:
                return episode

            return resolve_episode()

        return resolve_data

    episodes = (
        ResolvableEpisode(info=first_episode["info"], resolve_data=make_resolver("first", first_episode)),
        ResolvableEpisode(info=second_episode["info"], resolve_data=make_resolver("second", second_episode)),
    )
    validation_results = iter([True, False])

    async def fake_resolve_request(
        scope: ExecutionScope,
        request: DownloadRequest,
    ) -> ExtractorResolveOutcome:
        return ResolveOutcome(items=episodes)

    async def fake_validate_user_info(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        return next(validation_results)

    async def fake_process_download(
        scope: ExecutionScope,
        episode_data: EpisodeData,
        request: DownloadRequest,
    ) -> ItemResult:
        return ItemResult(state=ItemState.DONE, output_path=episode_data["info"]["path"])

    manager = DownloadManager()
    monkeypatch.setattr(manager, "resolve_request", fake_resolve_request)
    monkeypatch.setattr(download_manager_module, "validate_user_info", fake_validate_user_info)
    monkeypatch.setattr(download_manager_module, "process_download", fake_process_download)

    with pytest.raises(NotLoginError):
        await manager.process_request(
            ExecutionScope(cast("httpx.AsyncClient", object())),
            make_request(None),
        )

    # 第二个条目在校验失败前从未进入解析，因此连 coroutine 对象都不会创建。
    assert created_coroutines == ["first"]


@as_sync
async def test_execute_uses_request_scopes_and_keeps_path_resolver_order():
    requests = [
        DownloadRequest.model_validate(
            {
                "source": {"url": "BV1first"},
                "access": {"auth_profile": "first"},
                "network": {
                    "proxy": "no",
                    "fetch_workers": 2,
                    "download_workers": 3,
                },
            }
        ),
        DownloadRequest.model_validate(
            {
                "source": {"url": "BV1second"},
                "access": {"auth_profile": "second"},
                "network": {
                    "proxy": "auto",
                    "fetch_workers": 5,
                    "download_workers": 7,
                },
            }
        ),
    ]

    class RecordingManager(DownloadManager):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[ExecutionScope, str, str]] = []

        async def process_request(
            self,
            scope: ExecutionScope,
            request: DownloadRequest,
        ) -> tuple[ItemResult, ...]:
            path = self.unique_path("same/video.mp4")
            self.calls.append((scope, request.source.url, path))
            return (ItemResult(state=ItemState.DONE, output_path=Path(path)),)

    def resolve_credentials(request: DownloadRequest) -> AuthInfo:
        return cast(
            "AuthInfo",
            {
                "SESSDATA": f"{request.access.auth_profile},session",
                "bili_jct": None,
            },
        )

    manager = RecordingManager()
    result = await manager.execute(RequestExecutionScopeFactory(resolve_credentials), requests)

    assert [url for _, url, _ in manager.calls] == ["BV1first", "BV1second"]
    # unique_path 返回的字符串使用平台原生分隔符，按 Path 比较
    assert [Path(path) for _, _, path in manager.calls] == [
        Path("same/video.mp4"),
        Path("same/video (1).mp4"),
    ]
    first_scope, second_scope = (scope for scope, _, _ in manager.calls)
    assert first_scope is not second_scope
    assert first_scope.client is not second_scope.client
    assert first_scope.client.is_closed and second_scope.client.is_closed
    assert first_scope.fetch_limiter._value == 2
    assert first_scope.download_workers == 3
    assert second_scope.fetch_limiter._value == 5
    assert second_scope.download_workers == 7
    assert first_scope.fetch_limiter is not second_scope.fetch_limiter
    assert first_scope.client.cookies.get("SESSDATA") == "first%2Csession"
    assert second_scope.client.cookies.get("SESSDATA") == "second%2Csession"
    assert result == DownloadResult(
        items=(
            ItemResult(state=ItemState.DONE, output_path=Path("same/video.mp4")),
            ItemResult(state=ItemState.DONE, output_path=Path("same/video (1).mp4")),
        )
    )


@as_sync
async def test_execute_stops_on_failure_and_closes_client():
    requests = [
        DownloadRequest.model_validate({"source": {"url": "BV1first"}}),
        DownloadRequest.model_validate({"source": {"url": "BV1second"}}),
    ]

    class FailingManager(DownloadManager):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[str] = []
            self.client: httpx.AsyncClient | None = None

        async def process_request(
            self,
            scope: ExecutionScope,
            request: DownloadRequest,
        ) -> tuple[ItemResult, ...]:
            self.client = scope.client
            self.calls.append(request.source.url)
            raise WrongArgumentError("request failed")

    manager = FailingManager()
    with pytest.raises(WrongArgumentError, match="request failed"):
        await manager.execute(RequestExecutionScopeFactory(), requests)

    assert manager.calls == ["BV1first"]
    assert manager.client is not None and manager.client.is_closed


@as_sync
async def test_execute_cancellation_closes_client():
    started = asyncio.Event()
    release = asyncio.Event()
    request = DownloadRequest.model_validate({"source": {"url": "BV1cancel"}})

    class BlockingManager(DownloadManager):
        def __init__(self) -> None:
            super().__init__()
            self.client: httpx.AsyncClient | None = None

        async def process_request(
            self,
            scope: ExecutionScope,
            request: DownloadRequest,
        ) -> tuple[ItemResult, ...]:
            self.client = scope.client
            started.set()
            await release.wait()
            return ()

    manager = BlockingManager()
    execution = asyncio.create_task(manager.execute(RequestExecutionScopeFactory(), [request]))
    await started.wait()
    execution.cancel()

    with pytest.raises(asyncio.CancelledError):
        await execution

    assert manager.client is not None and manager.client.is_closed


@pytest.mark.processor
def test_ensure_unique_path_updates_episode_and_only_warns_on_rename():
    reports: list[tuple[str, ReportLevel]] = []
    resolved_paths: list[str] = []

    def resolve_unique_path(path: str) -> str:
        resolved_paths.append(path)
        return "group/video (1).mp4"

    renamed_episode = make_episode("group/video.mp4")
    with bind_download_report_sink(lambda message, level, _badge, _color: reports.append((message, level))):
        result = ensure_unique_path(renamed_episode, resolve_unique_path)
        unchanged_episode = make_episode("group/another.mp4")
        ensure_unique_path(unchanged_episode, lambda path: path)

    assert result is renamed_episode
    assert result["info"]["path"] == Path("group/video (1).mp4")
    assert result["info"]["listing"].planned_path == Path("group/video.mp4")
    assert resolved_paths == [str(Path("group/video.mp4"))]
    assert reports == [("文件名重复，已重命名为 video (1).mp4", ReportLevel.WARNING)]


@pytest.mark.processor
def test_show_batch_episode_title_preserves_order_and_group_state():
    output: list[tuple[str, str]] = []

    def capture_output(message: str, _level: Any, badge: str | None, _color: Any) -> None:
        assert badge is not None
        output.append((message, badge))

    current_group: str | None = None
    group_states: list[str | None] = []
    episodes = [
        make_episode("投稿 A/P1", "投稿 A"),
        make_episode("投稿 A/P2", "投稿 A"),
        make_episode("单集"),
        make_episode("投稿 B/P1", "投稿 B"),
    ]
    with bind_download_report_sink(capture_output):
        for index, episode in enumerate(episodes, start=1):
            current_group = show_batch_episode_title(episode["info"], index, len(episodes), current_group)
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
