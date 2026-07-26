from __future__ import annotations

import asyncio

import httpx
import pytest

from tests.test_processor.test_download_result import make_request, make_resource_only_episode
from yutto.core.execution import ExecutionScope
from yutto.downloader.planner import DownloadPlanner
from yutto.downloader.transfer import download_video_and_audio, slice_blocks
from yutto.utils.fetcher import Fetcher, create_client, unwrap_fetch_result
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.functional import as_sync

from ..conftest import TEST_DIR


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


@pytest.mark.processor
@as_sync
async def test_150_kB_downloader():
    # test_dir = "./downloader_test/"
    # url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    # 因为 file-examples-com 挂掉了（GitHub 账号都消失了，因此暂时使用一个别处的 mirror）
    url = "https://github.com/nhegde610/samples-files/raw/main/file_example_MP4_480_1_5MG.mp4"
    file_path = TEST_DIR / "test_150_kB.pdf"
    async with await AsyncFileBuffer.open(file_path, overwrite=False) as buffer:
        async with create_client(
            timeout=httpx.Timeout(7, connect=3),
        ) as client:
            scope = ExecutionScope(client, download_workers=4)
            size = unwrap_fetch_result(await Fetcher.get_size(scope, url))
            coroutines = [
                Fetcher.download_file_with_offset(scope, url, [], buffer, offset, block_size)
                for offset, block_size in slice_blocks(buffer.written_size, size, 1 * 1024 * 1024)
            ]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
    assert size == file_path.stat().st_size, "文件大小与实际大小不符"


@pytest.mark.processor
@as_sync
async def test_150_kB_no_slice_downloader():
    # test_dir = "./downloader_test/"
    # url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    url = "https://github.com/nhegde610/samples-files/raw/main/file_example_MP4_480_1_5MG.mp4"
    file_path = TEST_DIR / "test_150_kB_no_slice.pdf"
    async with await AsyncFileBuffer.open(file_path, overwrite=False) as buffer:
        async with create_client(
            timeout=httpx.Timeout(7, connect=3),
        ) as client:
            scope = ExecutionScope(client, download_workers=4)
            size = unwrap_fetch_result(await Fetcher.get_size(scope, url))
            coroutines = [Fetcher.download_file_with_offset(scope, url, [], buffer, 0, size)]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
    assert size == file_path.stat().st_size, "文件大小与实际大小不符"
