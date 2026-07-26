from __future__ import annotations

import httpx
import pytest
from returns.result import Failure

from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.execution import ExecutionScope
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.transfer import _probe_media_size, download_video_and_audio, slice_blocks
from yutto.exceptions import MaxRetryError
from yutto.utils.fetcher import Fetcher
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


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
