import asyncio
import random
from typing import Any, Callable, Coroutine, Literal, Optional, TypeVar, Union
from urllib.parse import quote, unquote

import aiohttp
from aiohttp import ClientSession

from yutto.exceptions import MaxRetryError
from yutto.utils.console.logger import Logger
from yutto.utils.file_buffer import AsyncFileBuffer

T = TypeVar("T")


class MaxRetry:
    """重试装饰器，为请求方法提供一定的重试次数

    Args:
        max_retry (int): 额外重试次数（如重试次数为 2，则最多尝试 3 次）
    """

    def __init__(self, max_retry: int = 2):
        self.max_retry = max_retry

    def __call__(self, connect_once: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        async def connect_n_times(*args: Any, **kwargs: Any) -> T:
            retry = self.max_retry + 1
            while retry:
                try:
                    return await connect_once(*args, **kwargs)
                except (
                    aiohttp.client_exceptions.ClientPayloadError,  # type: ignore
                    aiohttp.client_exceptions.ClientConnectorError,  # type: ignore
                    aiohttp.client_exceptions.ServerDisconnectedError,  # type: ignore
                ):
                    await asyncio.sleep(0.5)
                    Logger.warning(f"抓取失败，正在重试，剩余 {retry - 1} 次")
                except asyncio.TimeoutError:
                    Logger.warning(f"抓取超时，正在重试，剩余 {retry - 1} 次")
                finally:
                    retry -= 1
            raise MaxRetryError("超出最大重试次数！")

        return connect_n_times


class Fetcher:
    proxy: Optional[str] = None
    trust_env: bool = True
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }
    cookies = {}
    semaphore: asyncio.Semaphore = asyncio.Semaphore(8)  # 初始使用较小的信号量用于抓取信息，下载时会重新设置一个较大的值
    _touch_set: set[str] = set()

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
    def set_semaphore(cls, num_workers: int):
        Fetcher.semaphore = asyncio.Semaphore(num_workers)

    @classmethod
    @MaxRetry(2)
    async def fetch_text(cls, session: ClientSession, url: str, encoding: Optional[str] = None) -> Optional[str]:
        async with cls.semaphore:
            Logger.debug(f"Fetch text: {url}")
            Logger.status.next_tick()
            async with session.get(url, proxy=Fetcher.proxy) as resp:
                if not resp.ok:
                    return None
                return await resp.text(encoding=encoding)

    @classmethod
    @MaxRetry(2)
    async def fetch_bin(cls, session: ClientSession, url: str) -> Optional[bytes]:
        async with cls.semaphore:
            Logger.debug(f"Fetch bin: {url}")
            Logger.status.next_tick()
            async with session.get(url, proxy=Fetcher.proxy) as resp:
                if not resp.ok:
                    return None
                return await resp.read()

    @classmethod
    @MaxRetry(2)
    async def fetch_json(cls, session: ClientSession, url: str) -> Optional[Any]:
        async with cls.semaphore:
            Logger.debug(f"Fetch json: {url}")
            Logger.status.next_tick()
            async with session.get(url, proxy=Fetcher.proxy) as resp:
                if not resp.ok:
                    return None
                return await resp.json()

    @classmethod
    @MaxRetry(2)
    async def get_redirected_url(cls, session: ClientSession, url: str) -> str:
        # 关于为什么要前往重定向 url，是因为 B 站的 url 类型实在是太多了，比如有 b23.tv 的短链接
        # 为 SEO 的搜索引擎链接、甚至有的 av、BV 链接实际上是番剧页面，一一列举实在太麻烦，而且最后一种
        # 情况需要在 av、BV 解析一部分信息后才能知道是否是番剧页面，处理起来非常麻烦（bilili 就是这么做的）
        async with cls.semaphore:
            async with session.get(
                url,
                proxy=Fetcher.proxy,
                ssl=False,
            ) as resp:
                redirected_url = str(resp.url)
                if redirected_url == url:
                    Logger.debug(f"Get redircted url: {url}")
                else:
                    Logger.debug(f"Get redircted url: {url} -> {redirected_url}")
                Logger.status.next_tick()
                return redirected_url

    @classmethod
    @MaxRetry(2)
    async def get_size(cls, session: ClientSession, url: str) -> Optional[int]:
        async with cls.semaphore:
            headers = session.headers.copy()
            headers["Range"] = "bytes=0-1"
            async with session.get(
                url,
                headers=headers,
                proxy=Fetcher.proxy,
                ssl=False,
            ) as resp:
                if resp.status == 206:
                    size = int(resp.headers["Content-Range"].split("/")[-1])
                    Logger.debug(f"Get size: {url} {size}")
                    return size
                else:
                    return None

    @classmethod
    @MaxRetry(2)
    async def touch_url(cls, session: ClientSession, url: str):
        # 因为保持同一个 session，同样的页面没必要重复 touch
        if url in cls._touch_set:
            return
        cls._touch_set.add(url)
        async with cls.semaphore:
            Logger.debug(f"Torch url: {url}")
            async with session.get(
                url,
                proxy=Fetcher.proxy,
                ssl=False,
            ) as resp:
                resp.close()

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
        async with cls.semaphore:
            Logger.debug(f"Start download (offset {offset}) {url}")
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
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(connect=5, sock_read=10),
                        proxy=Fetcher.proxy,
                        ssl=False,
                    ) as resp:
                        if stream:
                            while True:
                                # 如果直接用 1KiB 的话，会产生大量的块，需要消耗大量的 CPU 资源来维持顺序，
                                # 而使用 1MiB 以上或者不使用流式下载方式时，由于分块太大，
                                # 导致进度条显示的实时速度并不准，波动太大，用户体验不佳，
                                # 因此取两者折中
                                chunk = await resp.content.read(2**16)
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

                except (
                    aiohttp.client_exceptions.ClientPayloadError,  # type: ignore
                    aiohttp.client_exceptions.ClientConnectorError,  # type: ignore
                    aiohttp.client_exceptions.ServerDisconnectedError,  # type: ignore
                ):
                    await asyncio.sleep(0.5)
                    Logger.warning(f"文件 {file_buffer.file_path} 下载出错，尝试重新连接...")

                except asyncio.TimeoutError:
                    Logger.warning(f"文件 {file_buffer.file_path} 下载超时，尝试重新连接...")
