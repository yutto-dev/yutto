from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Failure, Success

import yutto.downloader.transfer as transfer_module
from tests.helpers.http_range_server import LocalRangeServer, RangeFault
from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.events import DownloadEvent, DownloadProgress
from yutto.core.execution import ExecutionScope
from yutto.core.operation import bind_download_event_sink
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.progressbar import show_progress
from yutto.downloader.transfer import (
    _allocate_native_worker_batches,
    _probe_media_size,
    _wait_for_native_transfers,
    download_video_and_audio,
)
from yutto.exceptions import MaxRetryError
from yutto.utils.fetcher import Fetcher, create_client
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.processor


@as_sync
async def test_local_range_server_targets_faults_and_closes_connections():
    with LocalRangeServer(b"payload", faults=[((2, 3), RangeFault.IGNORE)]) as server:
        async with create_client(trust_env=False) as session:
            probe = await session.get(server.url, headers={"Range": "bytes=0-1"})
            faulted = await session.get(server.url, headers={"Range": "bytes=2-3"})

    assert probe.status_code == 206
    assert faulted.status_code == 200
    assert probe.header("Connection") == "close"
    assert faulted.header("Connection") == "close"


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[DownloadEvent] = []

    def emit(self, event: DownloadEvent) -> None:
        self.events.append(event)


@as_sync
async def test_native_resume_progress_does_not_count_existing_bytes_as_speed():
    page_size = 64 * 1024

    class Snapshot:
        def __init__(
            self,
            origin_bytes: int,
            received_bytes: int,
            committed_bytes: int,
            *,
            window_saturated: bool = False,
        ):
            self.origin_bytes = origin_bytes
            self.received_bytes = received_bytes
            self.committed_bytes = committed_bytes
            self.window_saturated = window_saturated

    class Handle:
        snapshots = iter([Snapshot(0, 0, 0), Snapshot(page_size, page_size, page_size)])

        def snapshot(self) -> Snapshot:
            return next(self.snapshots)

        def done(self) -> bool:
            return True

    sink = RecordingEventSink()
    with bind_download_event_sink(sink):
        await show_progress([Handle()], page_size * 2)

    assert sink.events == [
        DownloadProgress(
            current=page_size,
            total=page_size * 2,
            speed_per_second=0,
            buffered_bytes=0,
        )
    ]


@pytest.mark.parametrize("window_saturated", [False, True])
@as_sync
async def test_native_progress_uses_only_window_saturation_signal(window_saturated: bool):
    page_size = 64 * 1024

    class Snapshot:
        origin_bytes = 0
        received_bytes = 3 * page_size
        committed_bytes = page_size

        def __init__(self) -> None:
            self.window_saturated = window_saturated

    class Handle:
        def snapshot(self) -> Snapshot:
            return Snapshot()

        def done(self) -> bool:
            return True

    sink = RecordingEventSink()
    with bind_download_event_sink(sink):
        await show_progress([Handle()], 8 * page_size)

    assert len(sink.events) == 1
    assert isinstance(sink.events[0], DownloadProgress)
    assert sink.events[0].buffered_bytes == 2 * page_size
    assert sink.events[0].is_congested is window_saturated


@as_sync
async def test_probe_media_size_preserves_probe_failures(monkeypatch: pytest.MonkeyPatch):
    failures = {
        "primary": MaxRetryError("primary failed"),
        "mirror": MaxRetryError("mirror failed"),
    }

    async def get_size(_scope: ExecutionScope, url: str) -> Failure[MaxRetryError]:
        return Failure(failures[url])

    monkeypatch.setattr(Fetcher, "get_size", get_size)
    scope = ExecutionScope(cast("Any", object()))
    with pytest.raises(MaxRetryError) as single_failure:
        await _probe_media_size(scope, "primary", [])
    with pytest.raises(MaxRetryError) as multiple_failure:
        await _probe_media_size(scope, "primary", ["mirror"])

    assert single_failure.value is failures["primary"]
    assert isinstance(multiple_failure.value.__cause__, ExceptionGroup)
    assert set(multiple_failure.value.__cause__.exceptions) == set(failures.values())


@as_sync
async def test_probe_media_size_rejects_a_source_without_a_known_length(monkeypatch: pytest.MonkeyPatch):
    async def get_size(_scope: ExecutionScope, _url: str) -> Success[None]:
        return Success(None)

    monkeypatch.setattr(Fetcher, "get_size", get_size)
    with pytest.raises(MaxRetryError, match="未返回长度"):
        await _probe_media_size(ExecutionScope(cast("Any", object())), "primary", [])


@pytest.mark.parametrize(
    ("workers", "transfers", "expected"),
    [
        (8, 2, [[4, 4]]),
        (3, 2, [[2, 1]]),
        (1, 2, [[1], [1]]),
    ],
)
def test_native_worker_budget_is_global(workers: int, transfers: int, expected: list[list[int]]):
    assert _allocate_native_worker_batches(workers, transfers) == expected
    assert all(sum(batch) <= workers for batch in expected)


@as_sync
async def test_native_transfer_failure_uses_the_existing_cli_error_boundary():
    async def fail() -> int:
        raise RuntimeError("all sources exhausted")

    task = asyncio.create_task(fail())
    with pytest.raises(MaxRetryError, match="媒体下载失败：all sources exhausted") as failure:
        await _wait_for_native_transfers([task])

    assert isinstance(failure.value.__cause__, RuntimeError)


@as_sync
async def test_known_size_resume_uses_existing_contiguous_prefix(tmp_path):
    page_size = 64 * 1024
    resume_offset = page_size + 7
    payload = b"A" * page_size + b"B" * page_size + b"C" * page_size
    episode = make_resource_only_episode()

    with LocalRangeServer(payload) as server:
        episode["audios"] = [
            {
                "url": server.url,
                "mirrors": [],
                "codec": "mp4a",
                "width": 0,
                "height": 0,
                "quality": 30280,
            }
        ]
        plan = DownloadPlanner().plan(episode, make_request(tmp_path, audio=True))
        plan.paths.temporary_dir.mkdir(parents=True)
        plan.paths.audio.write_bytes(payload[:resume_offset])

        async with create_client(trust_env=False) as session:
            await download_video_and_audio(ExecutionScope(session), plan)

    assert [request.range_header for request in server.requests] == [
        "bytes=0-1",
        f"bytes={resume_offset}-{len(payload) - 1}",
    ]
    assert plan.paths.audio.read_bytes() == payload
    assert plan.paths.audio.stat().st_size == len(payload)


@as_sync
async def test_out_of_order_ranges_commit_an_exact_contiguous_file(tmp_path):
    page_size = 64 * 1024
    payload = b"A" * page_size + b"B" * page_size + b"C" * page_size
    episode = make_resource_only_episode()
    first_range = (0, page_size - 1)
    later_range = (page_size, 2 * page_size - 1)

    with LocalRangeServer(payload, release_after={first_range: later_range}) as server:
        episode["audios"] = [
            {
                "url": server.url,
                "mirrors": [],
                "codec": "mp4a",
                "width": 0,
                "height": 0,
                "quality": 30280,
            }
        ]
        base_request = make_request(tmp_path, audio=True)
        request_data = base_request.model_dump()
        request_data["network"]["block_size_bytes"] = page_size
        request = type(base_request).model_validate(request_data)
        plan = DownloadPlanner().plan(episode, request)
        plan.paths.temporary_dir.mkdir(parents=True)

        async with create_client(trust_env=False) as session:
            await download_video_and_audio(ExecutionScope(session), plan)

    assert plan.paths.audio.read_bytes() == payload
    assert plan.paths.audio.stat().st_size == len(payload)
    completed_ranges = [
        request.range_header for request in server.completed_requests if request.range_header != "bytes=0-1"
    ]
    first_range_header = f"bytes={first_range[0]}-{first_range[1]}"
    later_range_header = f"bytes={later_range[0]}-{later_range[1]}"
    assert completed_ranges.index(later_range_header) < completed_ranges.index(first_range_header)


@as_sync
async def test_native_transfer_resumes_by_default(tmp_path):
    page_size = 64 * 1024
    payload = b"A" * page_size + b"B" * page_size + b"C" * 17
    episode = make_resource_only_episode()

    with LocalRangeServer(payload) as server:
        episode["audios"] = [
            {
                "url": server.url,
                "mirrors": [],
                "codec": "mp4a",
                "width": 0,
                "height": 0,
                "quality": 30280,
            }
        ]
        base_request = make_request(tmp_path, audio=True)
        request_data = base_request.model_dump()
        request = type(base_request).model_validate(request_data)
        plan = DownloadPlanner().plan(episode, request)
        plan.paths.temporary_dir.mkdir(parents=True)
        plan.paths.audio.write_bytes(payload[:page_size])

        async with create_client(trust_env=False) as session:
            await download_video_and_audio(ExecutionScope(session), plan)

    assert plan.paths.audio.read_bytes() == payload
    range_headers = [request.range_header for request in server.requests]
    assert range_headers.count("bytes=0-1") == 1
    assert f"bytes={page_size}-{len(payload) - 1}" in range_headers


@as_sync
async def test_cancelling_rust_backend_stops_the_native_transfer(tmp_path):
    page_size = 64 * 1024
    payload = b"A" * page_size + b"B" * page_size + b"C" * page_size + b"D" * page_size
    episode = make_resource_only_episode()
    blocker = (page_size, 2 * page_size - 1)
    later_range = f"bytes={2 * page_size}-{3 * page_size - 1}"

    with LocalRangeServer(payload, delays={blocker: 0.2}) as server:
        episode["audios"] = [
            {
                "url": server.url,
                "mirrors": [],
                "codec": "mp4a",
                "width": 0,
                "height": 0,
                "quality": 30280,
            }
        ]
        base_request = make_request(tmp_path, audio=True)
        request_data = base_request.model_dump()
        request_data["network"]["block_size_bytes"] = page_size
        plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))
        plan.paths.temporary_dir.mkdir(parents=True)
        plan.paths.audio.write_bytes(payload[:page_size])

        async with create_client(trust_env=False) as session:
            task = asyncio.create_task(download_video_and_audio(ExecutionScope(session), plan))
            async with asyncio.timeout(2):
                while not any(request.range_header == later_range for request in server.completed_requests):
                    await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert plan.paths.audio.read_bytes() == payload[:page_size]
        await asyncio.sleep(0.25)

    assert plan.paths.audio.read_bytes() == payload[:page_size]


@as_sync
async def test_native_transfer_reuses_the_scope_session_and_maps_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict[str, Any] = {}

    class Snapshot:
        origin_bytes = 0
        received_bytes = 123
        committed_bytes = 123
        window_saturated = False

    class Handle:
        def done(self) -> bool:
            return True

        def cancel(self) -> None:
            raise AssertionError("completed handle must not be cancelled")

        def snapshot(self) -> Snapshot:
            return Snapshot()

        def result(self) -> int:
            return 123

    async def get_size(_scope: ExecutionScope, _url: str) -> Success[int]:
        return Success(123)

    class FakeSession:
        def start_transfer(self, *args: object, **kwargs: object) -> Handle:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return Handle()

    monkeypatch.setattr(Fetcher, "get_size", get_size)

    episode = make_resource_only_episode()
    episode["audios"] = [
        {
            "url": "https://primary.example/media",
            "mirrors": [
                "https://blocked.example/media",
                "https://mirror.example/media",
            ],
            "codec": "mp4a",
            "width": 0,
            "height": 0,
            "quality": 30280,
        }
    ]
    base_request = make_request(tmp_path, audio=True)
    request_data = base_request.model_dump()
    request_data["network"].update(
        {
            "banned_mirrors_pattern": "blocked",
            "block_size_bytes": 64 * 1024,
        }
    )
    plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))

    session = FakeSession()
    await download_video_and_audio(
        ExecutionScope(cast("Any", session), download_workers=3),
        plan,
    )

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert isinstance(args, tuple)
    assert isinstance(kwargs, dict)
    assert args[0] == ["https://primary.example/media", "https://mirror.example/media"]
    assert args[2] == 123
    assert kwargs["workers"] == 3
    assert kwargs["block_size"] == 64 * 1024


@as_sync
async def test_rust_backend_reaps_a_started_handle_when_later_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    class Handle:
        def __init__(self) -> None:
            self.cancelled = False
            self.reaped = False

        def done(self) -> bool:
            return self.reaped

        def cancel(self) -> None:
            self.cancelled = True

    handle = Handle()
    starts = 0

    async def get_size(_scope: ExecutionScope, _url: str) -> Success[int]:
        return Success(123)

    async def wait_for_transfer(started_handle: Handle, **_kwargs: object) -> int:
        while not started_handle.cancelled:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        started_handle.reaped = True
        raise RuntimeError("cancelled")

    class FakeSession:
        def start_transfer(self, *_args: object, **_kwargs: object) -> Handle:
            nonlocal starts
            starts += 1
            if starts == 2:
                raise RuntimeError("second setup failed")
            return handle

    monkeypatch.setattr(Fetcher, "get_size", get_size)
    monkeypatch.setattr(transfer_module, "wait_for_transfer", wait_for_transfer)

    episode = make_resource_only_episode()
    episode["videos"] = [
        {
            "url": "https://video.example/media",
            "mirrors": [],
            "codec": "avc",
            "width": 1920,
            "height": 1080,
            "quality": 80,
        }
    ]
    episode["audios"] = [
        {
            "url": "https://audio.example/media",
            "mirrors": [],
            "codec": "mp4a",
            "width": 0,
            "height": 0,
            "quality": 30280,
        }
    ]
    base_request = make_request(tmp_path, video=True, audio=True)
    request_data = base_request.model_dump()
    plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))

    with pytest.raises(RuntimeError, match="second setup failed"):
        await download_video_and_audio(
            ExecutionScope(cast("Any", FakeSession()), download_workers=2),
            plan,
        )

    assert handle.cancelled
    assert handle.reaped
