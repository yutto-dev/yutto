import pytest
import os
import aiohttp
import shutil

from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.fetcher import Fetcher
from yutto.processor.downloader import slice_blocks
from yutto.utils.asynclib import parallel_with_limit
from yutto.utils.functiontools.sync import sync


@pytest.mark.downloader
@sync
async def test_1_5_M_downloader():
    test_dir = "./downloader_test/"
    url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"
    video_path = os.path.join(test_dir, "test_1_5_M.mp4")
    if not os.path.exists(test_dir):
        os.mkdir(test_dir)
    buffer = await AsyncFileBuffer.create(video_path, overwrite=False)
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        size = await Fetcher.get_size(session, url)
        task_funcs = [
            Fetcher.download_file_with_offset(session, url, [], buffer, offset, block_size)
            for offset, block_size in slice_blocks(buffer.written_size, size, 1 * 1024 * 1024)
        ]

        tasks = parallel_with_limit(task_funcs, num_workers=4)
        print("开始下载……")
        for task in tasks:
            await task
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
    buffer = await AsyncFileBuffer.create(video_path, overwrite=False)
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        size = await Fetcher.get_size(session, url)
        task_funcs = [Fetcher.download_file_with_offset(session, url, [], buffer, 0, size)]

        tasks = parallel_with_limit(task_funcs, num_workers=4)
        print("开始下载……")
        for task in tasks:
            await task
        print("下载完成！")
        assert size == os.path.getsize(video_path), "文件大小与实际大小不符"
    shutil.rmtree(test_dir)


@pytest.mark.downloader
@sync
async def test_10_M_downloader():
    test_dir = "./downloader_test/"
    url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_1280_10MG.mp4"
    video_path = os.path.join(test_dir, "test_10_M.mp4")
    if not os.path.exists(test_dir):
        os.mkdir(test_dir)
    buffer = await AsyncFileBuffer.create(video_path, overwrite=False)
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        size = await Fetcher.get_size(session, url)
        task_funcs = [
            Fetcher.download_file_with_offset(session, url, [], buffer, offset, block_size)
            for offset, block_size in slice_blocks(buffer.written_size, size, 1 * 1024 * 1024)
        ]

        tasks = parallel_with_limit(task_funcs, num_workers=4)
        print("开始下载……")
        for task in tasks:
            await task
        print("下载完成！")
        assert size == os.path.getsize(video_path), "文件大小与实际大小不符"
    shutil.rmtree(test_dir)
