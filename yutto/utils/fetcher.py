import asyncio
import aiohttp
import random
from typing import Any, Optional

from aiohttp import ClientSession

from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.console.logger import Logger


class MaxRetryError(Exception):
    pass


class Fetcher:
    @classmethod
    async def fetch_text(cls, session: ClientSession, url: str, max_retry: int = 2) -> str:
        retry = max_retry + 1
        while retry:
            try:
                async with session.get(url) as resp:
                    return await resp.text()
            except asyncio.TimeoutError as e:
                Logger.warning("url: {url} 抓取超时".format(url=url))
            finally:
                retry -= 1
        raise MaxRetryError()

    @classmethod
    async def fetch_json(cls, session: ClientSession, url: str, max_retry: int = 2) -> Any:
        retry = max_retry + 1
        while retry:
            try:
                async with session.get(url) as resp:
                    return await resp.json()
            except asyncio.TimeoutError as e:
                Logger.warning("url: {url} 抓取超时".format(url=url))
            finally:
                retry -= 1
        raise MaxRetryError()

    @classmethod
    async def get_size(cls, session: ClientSession, url: str) -> Optional[int]:
        headers = session.headers.copy()
        headers["Range"] = "bytes=0-1"
        async with session.get(url, headers=headers) as resp:
            if resp.status == 206:
                return int(resp.headers["Content-Range"].split("/")[-1])
            else:
                return None

    @classmethod
    async def download_file_with_offset(
        cls,
        session: ClientSession,
        url: str,
        mirrors: list[str],
        file_buffer: AsyncFileBuffer,
        offset: int,
        size: Optional[int],
        stream: bool = True,
    ) -> None:
        done = False
        headers = session.headers.copy()
        url_pool = [url] + mirrors
        block_offset = 0
        while not done:
            try:
                url = random.choice(url_pool)
                headers["Range"] = "bytes={}-{}".format(
                    offset + block_offset, offset + size - 1 if size is not None else ""
                )
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(connect=5, sock_read=10)
                ) as resp:
                    if stream:
                        while True:
                            # 如果直接用 1KiB 的话，会产生大量的块，消耗大量的 CPU 资源，
                            # 反而使得协程的优势不明显
                            # 而使用 1MiB 以上或者不使用流式下载方式时，由于分块太大，
                            # 导致进度条显示的实时速度并不准，波动太大，用户体验不佳，
                            # 因此取两者折中
                            chunk = await resp.content.read(2 ** 15)
                            if not chunk:
                                break
                            await file_buffer.write(chunk, offset + block_offset)
                            block_offset += len(chunk)
                    else:
                        chunk = await resp.read()
                        await file_buffer.write(chunk, offset + block_offset)
                        block_offset += len(chunk)
                # TODO: 是否需要校验总大小
                done = True

            except asyncio.TimeoutError as e:
                Logger.warning("文件 {} 下载超时，尝试重新连接...".format(file_buffer.file_path))
