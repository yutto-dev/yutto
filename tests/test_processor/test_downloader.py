from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
import pytest
from returns.result import Failure, Success

from tests.helpers.http_range_server import LocalRangeServer, RangeFault
from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.events import DownloadEvent, DownloadProgress
from yutto.core.execution import ExecutionScope
from yutto.core.operation import bind_download_event_sink
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.progressbar import show_native_progress
from yutto.downloader.transfer import _probe_media_size, download_video_and_audio, slice_blocks
from yutto.exceptions import MaxRetryError
from yutto.utils.fetcher import Fetcher
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

pytestmark = pytest.mark.processor


@as_sync
async def test_local_range_server_targets_faults_and_closes_connections():
    with LocalRangeServer(b"payload", faults=[((2, 3), RangeFault.IGNORE)]) as server:
        async with httpx.AsyncClient(http2=False) as client:
            probe = await client.get(server.url, headers={"Range": "bytes=0-1"})
            faulted = await client.get(server.url, headers={"Range": "bytes=2-3"})

    assert probe.status_code == 206
    assert faulted.status_code == 200
    assert probe.headers["Connection"] == "close"
    assert faulted.headers["Connection"] == "close"


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[DownloadEvent] = []

    def emit(self, event: DownloadEvent) -> None:
        self.events.append(event)


@pytest.mark.parametrize(
    ("start", "total_size", "block_size", "expected"),
    [
        (7, 20, None, [(7, 13)]),
        (20, 20, None, []),
        (7, 21, 5, [(7, 5), (12, 5), (17, 4)]),
    ],
)
def test_slice_blocks_handles_resume_offsets(
    start: int,
    total_size: int,
    block_size: int | None,
    expected: list[tuple[int, int]],
):
    assert slice_blocks(start, total_size, block_size) == expected


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
        await show_native_progress([Handle()], page_size * 2)

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
        await show_native_progress([Handle()], 8 * page_size)

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
    async with httpx.AsyncClient() as client:
        scope = ExecutionScope(client)
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
    async with httpx.AsyncClient() as client:
        with pytest.raises(MaxRetryError, match="未返回长度"):
            await _probe_media_size(ExecutionScope(client), "primary", [])


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

        async with httpx.AsyncClient(http2=False) as client:
            await download_video_and_audio(ExecutionScope(client), plan)

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

        async with httpx.AsyncClient(http2=False) as client:
            await download_video_and_audio(ExecutionScope(client), plan)

    assert plan.paths.audio.read_bytes() == payload
    assert plan.paths.audio.stat().st_size == len(payload)
    completed_ranges = [
        request.range_header for request in server.completed_requests if request.range_header != "bytes=0-1"
    ]
    first_range_header = f"bytes={first_range[0]}-{first_range[1]}"
    later_range_header = f"bytes={later_range[0]}-{later_range[1]}"
    assert completed_ranges.index(later_range_header) < completed_ranges.index(first_range_header)


@as_sync
async def test_cancellation_keeps_only_the_committed_contiguous_prefix(tmp_path):
    page_size = 64 * 1024
    committed_prefix = b"A" * page_size
    payload = b"A" * page_size + b"B" * page_size + b"C" * page_size
    prefix_committed = asyncio.Event()
    later_range_buffered = asyncio.Event()

    class BlockingFirstRange(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield committed_prefix
            prefix_committed.set()
            await asyncio.Event().wait()

    class ObservableRange(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload[2 * page_size :]
            later_range_buffered.set()

    def handle_range(request: httpx.Request) -> httpx.Response:
        range_header = request.headers["Range"]
        if range_header == "bytes=0-1":
            return httpx.Response(
                206,
                content=payload[:2],
                headers={"Content-Range": f"bytes 0-1/{len(payload)}"},
            )
        if range_header == f"bytes=0-{2 * page_size - 1}":
            return httpx.Response(
                206,
                stream=BlockingFirstRange(),
                headers={"Content-Range": f"bytes 0-{2 * page_size - 1}/{len(payload)}"},
            )
        if range_header == f"bytes={2 * page_size}-{3 * page_size - 1}":
            return httpx.Response(
                206,
                stream=ObservableRange(),
                headers={"Content-Range": (f"bytes {2 * page_size}-{3 * page_size - 1}/{len(payload)}")},
            )
        raise AssertionError(f"unexpected Range: {range_header}")

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
    base_request = make_request(tmp_path, audio=True)
    request_data = base_request.model_dump()
    request_data["network"]["block_size_bytes"] = 2 * page_size
    plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))
    plan.paths.temporary_dir.mkdir(parents=True)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle_range)) as client:
        task = asyncio.create_task(download_video_and_audio(ExecutionScope(client), plan))
        try:
            await asyncio.wait_for(
                asyncio.gather(prefix_committed.wait(), later_range_buffered.wait()),
                timeout=2,
            )
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    assert plan.paths.audio.read_bytes() == committed_prefix


@as_sync
async def test_explicit_rust_backend_resumes_with_native_transfer(tmp_path):
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
        request_data["network"]["download_backend"] = "rust"
        request = type(base_request).model_validate(request_data)
        plan = DownloadPlanner().plan(episode, request)
        plan.paths.temporary_dir.mkdir(parents=True)
        plan.paths.audio.write_bytes(payload[:page_size])

        async with httpx.AsyncClient(http2=False) as client:
            await download_video_and_audio(ExecutionScope(client), plan)

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
        request_data["network"]["download_backend"] = "rust"
        request_data["network"]["block_size_bytes"] = page_size
        plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))
        plan.paths.temporary_dir.mkdir(parents=True)
        plan.paths.audio.write_bytes(payload[:page_size])

        async with httpx.AsyncClient(http2=False) as client:
            task = asyncio.create_task(download_video_and_audio(ExecutionScope(client), plan))
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
async def test_rust_backend_maps_mirrors_headers_cookies_proxy_and_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    import yutto_core

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

    async def legacy_download(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Rust backend must not fall back to the Python downloader")

    def start_transfer(*args: object, **kwargs: object) -> Handle:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Handle()

    monkeypatch.setattr(Fetcher, "get_size", get_size)
    monkeypatch.setattr(Fetcher, "download_file_with_offset", legacy_download)
    monkeypatch.setattr(yutto_core, "start_transfer", start_transfer)

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
            "download_backend": "rust",
            "banned_mirrors_pattern": "blocked",
            "block_size_bytes": 64 * 1024,
        }
    )
    plan = DownloadPlanner().plan(episode, type(base_request).model_validate(request_data))

    async with httpx.AsyncClient(headers={"X-Test": "value"}, cookies={"SESSDATA": "secret"}) as client:
        await download_video_and_audio(
            ExecutionScope(
                client,
                download_workers=3,
                proxy="socks5://127.0.0.1:1080",
                trust_env=False,
            ),
            plan,
        )

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert isinstance(args, tuple)
    assert isinstance(kwargs, dict)
    assert args[0] == ["https://primary.example/media", "https://mirror.example/media"]
    assert args[2] == 123
    assert kwargs["headers"]["x-test"] == "value"
    assert kwargs["headers"]["cookie"] == "SESSDATA=secret"
    assert kwargs["proxy"] == "socks5://127.0.0.1:1080"
    assert kwargs["use_system_proxy"] is False
    assert kwargs["workers"] == 3
    assert kwargs["block_size"] == 64 * 1024
