from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import quote, unquote

# Temporary fix for h2 stubs not found error by using `type: ignore`,
# it may be fixed in the next release. The key PR https://github.com/python-hyper/h2/pull/1289
# has been merged in the master branch
import h2.exceptions  # type: ignore
import httpx
from httpx import AsyncClient
from typing_extensions import ParamSpec

from yutto.exceptions import MaxRetryError
from yutto.utils.asynclib import async_cache
from yutto.utils.console.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping

    from yutto.utils.file_buffer import AsyncFileBuffer

RetT = TypeVar("RetT")
InputT = ParamSpec("InputT")


class MaxRetry:
    """重试装饰器，为请求方法提供一定的重试次数

    ### Args

    - max_retry (int): 额外重试次数（如重试次数为 2，则最多尝试 3 次）
    """

    def __init__(self, max_retry: int = 2):
        self.max_retry = max_retry

    def __call__(
        self, connect_once: Callable[InputT, Coroutine[Any, Any, RetT]]
    ) -> Callable[InputT, Coroutine[Any, Any, RetT]]:
        async def connect_n_times(*args: InputT.args, **kwargs: InputT.kwargs) -> RetT:
            retry = self.max_retry + 1
            while retry:
                try:
                    return await connect_once(*args, **kwargs)
                except httpx.TimeoutException:
                    Logger.warning(f"抓取超时，正在重试，剩余 {retry - 1} 次")
                except (httpx.InvalidURL, httpx.UnsupportedProtocol) as e:
                    raise e
                except httpx.HTTPError as e:
                    await asyncio.sleep(0.5)
                    error_type = e.__class__.__name__
                    Logger.warning(f"抓取失败（{error_type}），正在重试，剩余 {retry - 1} 次")
                finally:
                    retry -= 1
            raise MaxRetryError("超出最大重试次数！")

        return connect_n_times


DEFAULT_PROXY = None
DEFAULT_TRUST_ENV = True
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}
DEFAULT_COOKIES = httpx.Cookies()


class FetcherContext:
    proxy: str | None
    trust_env: bool
    headers: dict[str, str]
    cookies: httpx.Cookies
    fetch_semaphore: asyncio.Semaphore | None
    download_semaphore: asyncio.Semaphore | None

    def __init__(
        self,
        *,
        proxy: str | None = DEFAULT_PROXY,
        trust_env: bool = DEFAULT_TRUST_ENV,
        headers: dict[str, str] = DEFAULT_HEADERS,
        cookies: httpx.Cookies = DEFAULT_COOKIES,
    ):
        self.proxy = proxy
        self.trust_env = trust_env
        self.headers = headers
        self.cookies = cookies
        self.fetch_semaphore = None
        self.download_semaphore = None

    def set_fetch_semaphore(self, fetch_workers: int):
        self.fetch_semaphore = asyncio.Semaphore(fetch_workers)

    def set_download_semaphore(self, download_workers: int):
        self.download_semaphore = asyncio.Semaphore(download_workers)

    def set_sessdata(self, sessdata: str):
        self.cookies = httpx.Cookies()
        # 先解码后编码是防止获取到的 SESSDATA 是已经解码后的（包含「,」）
        # 而番剧无法使用解码后的 SESSDATA
        self.cookies.set("SESSDATA", quote(unquote(sessdata)))

    def set_proxy(self, proxy: str):
        if proxy == "auto":
            self.proxy = None
            self.trust_env = True
        elif proxy == "no":
            self.proxy = None
            self.trust_env = False
        else:
            self.proxy = proxy
            self.trust_env = False

    @asynccontextmanager
    async def fetch_guard(self):
        if self.fetch_semaphore is None:
            yield
            return
        async with self.fetch_semaphore:
            yield

    @asynccontextmanager
    async def download_guard(self):
        if self.download_semaphore is None:
            yield
            return
        async with self.download_semaphore:
            yield


class Fetcher:
    @staticmethod
    @MaxRetry(2)
    async def fetch_text(
        ctx: FetcherContext,
        client: AsyncClient,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        encoding: str | None = None,  # TODO(SigureMo): Support this
    ) -> str | None:
        async with ctx.fetch_guard():
            Logger.debug(f"Fetch text: {url}")
            Logger.status.next_tick()
            resp = await client.get(url, params=params)
            if resp.status_code != httpx.codes.OK:
                return None
            return resp.text

    @staticmethod
    @MaxRetry(2)
    async def fetch_bin(
        ctx: FetcherContext,
        client: AsyncClient,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> bytes | None:
        async with ctx.fetch_guard():
            Logger.debug(f"Fetch bin: {url}")
            Logger.status.next_tick()
            resp = await client.get(url, params=params)
            if resp.status_code != httpx.codes.OK:
                return None
            return resp.read()

    @staticmethod
    @MaxRetry(2)
    async def fetch_json(
        ctx: FetcherContext,
        client: AsyncClient,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Any | None:
        async with ctx.fetch_guard():
            Logger.debug(f"Fetch json: {url}")
            Logger.status.next_tick()
            resp = await client.get(url, params=params)
            if resp.status_code != httpx.codes.OK:
                return None
            return resp.json()

    @staticmethod
    @MaxRetry(2)
    async def get_redirected_url(ctx: FetcherContext, client: AsyncClient, url: str) -> str:
        # 关于为什么要前往重定向 url，是因为 B 站的 url 类型实在是太多了，比如有 b23.tv 的短链接
        # 为 SEO 的搜索引擎链接、甚至有的 av、BV 链接实际上是番剧页面，一一列举实在太麻烦，而且最后一种
        # 情况需要在 av、BV 解析一部分信息后才能知道是否是番剧页面，处理起来非常麻烦（bilili 就是这么做的）
        async with ctx.fetch_guard():
            resp = await client.get(url)
            redirected_url = str(resp.url)
            if redirected_url == url:
                Logger.debug(f"Get redircted url: {url}")
            else:
                Logger.debug(f"Get redircted url: {url} -> {redirected_url}")
            Logger.status.next_tick()
            return redirected_url

    @staticmethod
    @MaxRetry(2)
    async def get_size(ctx: FetcherContext, client: AsyncClient, url: str) -> int | None:
        async with ctx.fetch_guard():
            headers = client.headers.copy()
            headers["Range"] = "bytes=0-1"
            resp = await client.get(
                url,
                headers=headers,
            )
            if resp.status_code == 206:
                size = int(resp.headers["Content-Range"].split("/")[-1])
                Logger.debug(f"Get size: {url} {size}")
                return size
            else:
                return None

    @staticmethod
    @MaxRetry(2)
    # 对于相同 session，同样的页面没必要重复 touch
    @async_cache(lambda args: f"client_id={id(args.arguments['client'])}, url={args.arguments['url']}")
    async def touch_url(ctx: FetcherContext, client: AsyncClient, url: str):
        async with ctx.fetch_guard():
            Logger.debug(f"Touch url: {url}")
            await client.get(url)

    @staticmethod
    async def download_file_with_offset(
        ctx: FetcherContext,
        client: AsyncClient,
        url: str,
        mirrors: list[str],
        file_buffer: AsyncFileBuffer,
        offset: int,
        size: int | None,
    ) -> None:
        async with ctx.download_guard():
            Logger.debug(f"Start download (offset {offset}, number of mirrors {len(mirrors)}) {url}")
            done = False
            headers = client.headers.copy()
            url_pool = [url] + mirrors
            block_offset = 0
            while not done:
                try:
                    url = random.choice(url_pool)
                    headers["Range"] = "bytes={}-{}".format(
                        offset + block_offset, offset + size - 1 if size is not None else ""
                    )
                    async with client.stream(
                        "GET",
                        url,
                        headers=headers,
                        timeout=httpx.Timeout(7, connect=3),
                    ) as resp:
                        # 如果直接用 1KiB 的话，会产生大量的块，需要消耗大量的 CPU 资源来维持顺序，
                        # 而使用 1MiB 以上或者不使用流式下载方式时，由于分块太大，
                        # 导致进度条显示的实时速度并不准，波动太大，用户体验不佳，
                        # 因此取两者折中
                        async for chunk in resp.aiter_bytes(2**16):
                            await file_buffer.write(chunk, offset + block_offset)
                            block_offset += len(chunk)
                    # TODO: 是否需要校验总大小
                    done = True

                except httpx.TimeoutException:
                    Logger.warning(f"文件 {file_buffer.file_path} 下载超时，尝试重新连接...")
                    Logger.debug(f"超时链接：{url}")
                except (httpx.HTTPError, h2.exceptions.H2Error) as e:
                    await asyncio.sleep(0.5)
                    error_type = e.__class__.__name__
                    Logger.warning(f"文件 {file_buffer.file_path} 下载出错（{error_type}），尝试重新连接...")
                    Logger.debug(f"超时链接：{url}")
                except ValueError as e:
                    # 由于 httpx 经常出现此问题，暂时捕获该问题
                    if "semaphore released too many times" not in str(e):
                        raise e
                    Logger.warning(f"文件 {file_buffer.file_path} 下载出错（{e}），尝试重新连接...")


def create_client(
    headers: dict[str, str] = DEFAULT_HEADERS,
    cookies: httpx.Cookies = DEFAULT_COOKIES,
    trust_env: bool = DEFAULT_TRUST_ENV,
    proxy: str | None = DEFAULT_PROXY,
    timeout: int | httpx.Timeout = 5,
) -> AsyncClient:
    client = httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        trust_env=trust_env,
        proxy=proxy,
        timeout=timeout,
        follow_redirects=True,
        http2=True,
        verify=False,
    )
    return client
