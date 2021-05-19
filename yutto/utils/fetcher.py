import asyncio
import random
from typing import Any, Callable, Coroutine, Literal, Optional, TypeVar, Union
from urllib.parse import quote, unquote

import aiohttp
from aiohttp import ClientSession

from yutto.utils.console.logger import Logger
from yutto.utils.file_buffer import AsyncFileBuffer


class MaxRetryError(Exception):
    pass


T = TypeVar("T")


class MaxRetry:
    def __init__(self, max_retry: int = 2):
        self.max_retry = max_retry

    def __call__(self, connect_once: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        async def connect_n_times(*args: Any, **kwargs: Any) -> T:
            retry = self.max_retry + 1
            while retry:
                try:
                    return await connect_once(*args, **kwargs)
                except asyncio.TimeoutError as e:
                    Logger.warning("抓取超时，正在重试")
                finally:
                    retry -= 1
            raise MaxRetryError()

        return connect_n_times


class Fetcher:
    proxy: Optional[str] = None
    trust_env: bool = True
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }
    cookies = {}

    @classmethod
    def set_proxy(cls, proxy: Union[Literal["no", "auto"], str]):
        if proxy == "auto":
            Fetcher.proxy = None
            Fetcher.trust_env = True
        elif proxy == "no":
            Fetcher.proxy = None
            Fetcher.trust_env = False
        else:
            Fetcher.proxy = proxy
            Fetcher.trust_env = False

    @classmethod
    def set_sessdata(cls, sessdata: str):
        # 先解码后编码是防止获取到的 SESSDATA 是已经解码后的（包含「,」）
        # 而番剧无法使用解码后的 SESSDATA
        Fetcher.cookies = {"SESSDATA": quote(unquote(sessdata))}

    @classmethod
    @MaxRetry(2)
    async def fetch_text(cls, session: ClientSession, url: str, encoding: Optional[str] = None) -> str:
        async with session.get(url, proxy=Fetcher.proxy) as resp:
            return await resp.text(encoding=encoding)

    @classmethod
    @MaxRetry(2)
    async def fetch_bin(cls, session: ClientSession, url: str) -> bytes:
        async with session.get(url, proxy=Fetcher.proxy) as resp:
            return await resp.read()

    @classmethod
    @MaxRetry(2)
    async def fetch_json(cls, session: ClientSession, url: str) -> Any:
        async with session.get(url, proxy=Fetcher.proxy) as resp:
            return await resp.json()

    @classmethod
    @MaxRetry(2)
    async def get_redirected_url(cls, session: ClientSession, url: str) -> str:
        async with session.get(url, proxy=Fetcher.proxy) as resp:
            return str(resp.url)

    @classmethod
    @MaxRetry(2)
    async def get_size(cls, session: ClientSession, url: str) -> Optional[int]:
        headers = session.headers.copy()
        headers["Range"] = "bytes=0-1"
        async with session.get(url, headers=headers, proxy=Fetcher.proxy) as resp:
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
                    url, headers=headers, timeout=aiohttp.ClientTimeout(connect=5, sock_read=10), proxy=Fetcher.proxy
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
