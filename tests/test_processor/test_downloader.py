from __future__ import annotations

import httpx
import pytest

from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.execution import ExecutionScope
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.transfer import download_video_and_audio, slice_blocks
from yutto.utils.functional import as_sync


@pytest.mark.processor
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


@pytest.mark.processor
@as_sync
async def test_unknown_size_restarts_fragment_when_server_ignores_range(tmp_path):
    payload = b"A" * (64 * 1024) + b"B" * (64 * 1024)

    def ignore_range(_request: httpx.Request) -> httpx.Response:
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

    assert plan.paths.audio.read_bytes() == payload
