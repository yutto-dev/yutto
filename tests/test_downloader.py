import asyncio
import os
import shutil

import aiohttp
import pytest

from yutto.processor.downloader import slice_blocks
from yutto.utils.fetcher import Fetcher
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.functools import sync


@pytest.mark.downloader
@sync
async def test_1_5_M_downloader():
    test_dir = "./downloader_test/"
    url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    video_path = os.path.join(test_dir, "test_1_5_M.mp4")
    if not os.path.exists(test_dir):
        os.mkdir(test_dir)
    async with await AsyncFileBuffer(video_path, overwrite=False) as buffer:
        async with aiohttp.ClientSession(
            headers=Fetcher.headers,
            cookies=Fetcher.cookies,
            trust_env=Fetcher.trust_env,
            timeout=aiohttp.ClientTimeout(connect=5, sock_read=10),
        ) as session:
            Fetcher.set_semaphore(4)
            size = await Fetcher.get_size(session, url)
            coroutines = [
                Fetcher.download_file_with_offset(session, url, [], buffer, offset, block_size)
                for offset, block_size in slice_blocks(buffer.written_size, size, 1 * 1024 * 1024)
            ]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
            assert size == os.path.getsize(video_path), "文件大小与实际大小不符"
    shutil.rmtree(test_dir)


@pytest.mark.downloader
@sync
async def test_1_5_M_no_slice_downloader():
    test_dir = "./downloader_test/"
    url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    video_path = os.path.join(test_dir, "test_1_5_M.mp4")
    if not os.path.exists(test_dir):
        os.mkdir(test_dir)
    async with await AsyncFileBuffer(video_path, overwrite=False) as buffer:
        async with aiohttp.ClientSession(
            headers=Fetcher.headers,
            cookies=Fetcher.cookies,
            trust_env=Fetcher.trust_env,
            timeout=aiohttp.ClientTimeout(connect=5, sock_read=10),
        ) as session:
            Fetcher.set_semaphore(4)
            size = await Fetcher.get_size(session, url)
            coroutines = [Fetcher.download_file_with_offset(session, url, [], buffer, 0, size)]

            print("开始下载……")
            await asyncio.gather(*coroutines)
            print("下载完成！")
            assert size == os.path.getsize(video_path), "文件大小与实际大小不符"
    shutil.rmtree(test_dir)
