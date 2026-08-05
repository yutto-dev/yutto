from __future__ import annotations

import asyncio

import httpx
import pytest
from returns.result import Failure

from tests.helpers.http_range_server import LocalRangeServer, RangeFault
from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.execution import ExecutionScope
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.transfer import _probe_media_size, download_video_and_audio, slice_blocks
from yutto.exceptions import MaxRetryError
from yutto.utils.fetcher import Fetcher
from yutto.utils.functional import as_sync

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


@pytest.mark.parametrize(
    ("start", "total_size", "block_size", "expected"),
    [
        (7, None, 512, [(0, None)]),
        (7, 20, None, [(7, 13)]),
        (20, 20, None, []),
        (7, 21, 5, [(7, 5), (12, 5), (17, 4)]),
    ],
)
def test_slice_blocks_handles_resume_offsets(
    start: int,
    total_size: int | None,
    block_size: int | None,
    expected: list[tuple[int, int | None]],
):
    assert slice_blocks(start, total_size, block_size) == expected


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
async def test_unknown_size_restarts_fragment_and_http_200_retry(tmp_path):
    payload = b"A" * (64 * 1024) + b"B" * (64 * 1024)
    download_attempts = 0
    range_headers: list[str] = []

    class InterruptAfterFirstChunk(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload[: 64 * 1024]
            raise httpx.ReadTimeout("interrupted")

    def ignore_range(request: httpx.Request) -> httpx.Response:
        nonlocal download_attempts
        range_header = request.headers["Range"]
        range_headers.append(range_header)
        if range_header == "bytes=0-1":
            return httpx.Response(200, content=payload)
        download_attempts += 1
        if download_attempts == 1:
            return httpx.Response(200, stream=InterruptAfterFirstChunk())
        return httpx.Response(200, content=payload)

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
    plan = DownloadPlanner().plan(episode, make_request(tmp_path, audio=True))
    plan.paths.temporary_dir.mkdir(parents=True)
    plan.paths.audio.write_bytes(payload[: 64 * 1024])

    async with httpx.AsyncClient(transport=httpx.MockTransport(ignore_range)) as client:
        await download_video_and_audio(ExecutionScope(client), plan)

    assert range_headers == ["bytes=0-1", "bytes=0-", f"bytes={64 * 1024}-"]
    assert plan.paths.audio.read_bytes() == payload


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
