from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar, cast
from urllib.parse import quote, unquote, urlparse

import httpx
from returns.result import Failure, Result, Success
from typing_extensions import ParamSpec

from yutto.core.operation import ReportLevel, emit_download_report
from yutto.exceptions import MaxRetryError

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping

    from httpx import AsyncClient

    from yutto.auth import AuthInfo
    from yutto.core.execution import ExecutionScope

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
    ) -> Callable[InputT, Coroutine[Any, Any, Result[RetT, MaxRetryError]]]:
        async def connect_n_times(*args: InputT.args, **kwargs: InputT.kwargs) -> Result[RetT, MaxRetryError]:
            retry = self.max_retry + 1
            while retry:
                try:
                    return Success(await connect_once(*args, **kwargs))
                except httpx.TimeoutException:
                    emit_download_report(
                        f"抓取超时，正在重试，剩余 {retry - 1} 次",
                        level=ReportLevel.WARNING,
                    )
                except (httpx.InvalidURL, httpx.UnsupportedProtocol) as e:
                    raise e
                except httpx.HTTPError as e:
                    await asyncio.sleep(0.5)
                    error_type = e.__class__.__name__
                    emit_download_report(
                        f"抓取失败（{error_type}），正在重试，剩余 {retry - 1} 次",
                        level=ReportLevel.WARNING,
                    )
                finally:
                    retry -= 1
            return Failure(MaxRetryError("超出最大重试次数！"))

        return connect_n_times


def unwrap_fetch_result(result: Result[RetT, MaxRetryError]) -> RetT:
    match result:
        case Success(value):
            return cast("RetT", value)
        case Failure(error):
            raise cast("MaxRetryError", error)
    raise AssertionError("无法解析响应结果")


DEFAULT_PROXY = None
DEFAULT_TRUST_ENV = True
DEFAULT_FETCH_WORKERS = 8
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}
DEFAULT_COOKIES = httpx.Cookies()
SUPPORTED_PROXY_SCHEMES = frozenset({"http", "https", "socks5", "socks5h"})


def resolve_proxy(proxy: str) -> tuple[str | None, bool]:
    if proxy == "auto":
        return None, True
    if proxy == "no":
        return None, False

    parsed = urlparse(proxy)
    if not parsed.scheme or parsed.scheme not in SUPPORTED_PROXY_SCHEMES:
        raise ValueError(f"proxy 参数值（{proxy}）错误啦！")
    return proxy, False


def cookies_from_auth(auth_info: AuthInfo | None) -> httpx.Cookies:
    cookies = httpx.Cookies()
    if auth_info is None:
        return cookies
    # 先解码后编码是防止获取到的 SESSDATA 是已经解码后的（包含「,」）
    # 而番剧无法使用解码后的 SESSDATA
    cookies.set("SESSDATA", quote(unquote(auth_info["SESSDATA"])))
    if auth_info["bili_jct"]:
        cookies.set("bili_jct", auth_info["bili_jct"])
    return cookies


class Fetcher:
    @staticmethod
    @MaxRetry(2)
    async def fetch_text(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        encoding: str | None = None,  # TODO(SigureMo): Support this
    ) -> str | None:
        async with scope.fetch_guard():
            emit_download_report(f"Fetch text: {url}", level=ReportLevel.DEBUG)
            resp = await scope.client.get(url, params=params)
            if not resp.is_success:
                return None
            return resp.text

    @staticmethod
    @MaxRetry(2)
    async def fetch_bin(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> bytes | None:
        async with scope.fetch_guard():
            emit_download_report(f"Fetch bin: {url}", level=ReportLevel.DEBUG)
            resp = await scope.client.get(url, params=params)
            if not resp.is_success:
                return None
            return resp.read()

    @staticmethod
    @MaxRetry(2)
    async def fetch_json(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        async with scope.fetch_guard():
            emit_download_report(f"Fetch json: {url}", level=ReportLevel.DEBUG)
            resp = await scope.client.get(url, params=params)
            if not resp.is_success:
                resp.raise_for_status()
            return resp.json()

    @staticmethod
    @MaxRetry(2)
    async def get_redirected_url(scope: ExecutionScope, url: str) -> str:
        # 关于为什么要前往重定向 url，是因为 B 站的 url 类型实在是太多了，比如有 b23.tv 的短链接
        # 为 SEO 的搜索引擎链接、甚至有的 av、BV 链接实际上是番剧页面，一一列举实在太麻烦，而且最后一种
        # 情况需要在 av、BV 解析一部分信息后才能知道是否是番剧页面，处理起来非常麻烦（bilili 就是这么做的）
        async with scope.fetch_guard():
            resp = await scope.client.get(url)
            redirected_url = str(resp.url)
            if redirected_url == url:
                emit_download_report(f"Get redircted url: {url}", level=ReportLevel.DEBUG)
            else:
                emit_download_report(
                    f"Get redircted url: {url} -> {redirected_url}",
                    level=ReportLevel.DEBUG,
                )
            return redirected_url

    @staticmethod
    @MaxRetry(2)
    async def get_size(scope: ExecutionScope, url: str) -> int | None:
        async with scope.fetch_guard():
            headers = scope.client.headers.copy()
            headers["Range"] = "bytes=0-1"
            resp = await scope.client.get(
                url,
                headers=headers,
            )
            if resp.status_code == 206:
                size = int(resp.headers["Content-Range"].split("/")[-1])
                emit_download_report(f"Get size: {url} {size}", level=ReportLevel.DEBUG)
                return size
            else:
                return None

    @staticmethod
    @MaxRetry(2)
    async def touch_url(scope: ExecutionScope, url: str) -> None:
        if url in scope.touched_urls:
            emit_download_report(f"touch_url cache hit: {url}", level=ReportLevel.DEBUG)
            return
        async with scope.fetch_guard():
            emit_download_report(f"Touch url: {url}", level=ReportLevel.DEBUG)
            await scope.client.get(url)
            scope.touched_urls.add(url)


def _client_kwargs(
    *,
    headers: dict[str, str],
    cookies: httpx.Cookies,
    trust_env: bool,
    proxy: str | None,
    timeout: int | httpx.Timeout,
    http2: bool,
    verify: bool,
) -> dict[str, Any]:
    return {
        "headers": headers,
        "cookies": cookies,
        "trust_env": trust_env,
        "proxy": proxy,
        "timeout": timeout,
        "follow_redirects": True,
        "http2": http2,
        "verify": verify,
    }


def create_client(
    headers: dict[str, str] = DEFAULT_HEADERS,
    cookies: httpx.Cookies = DEFAULT_COOKIES,
    trust_env: bool = DEFAULT_TRUST_ENV,
    proxy: str | None = DEFAULT_PROXY,
    timeout: int | httpx.Timeout = 5,
    *,
    http2: bool = True,
    verify: bool = False,
) -> AsyncClient:
    client = httpx.AsyncClient(
        **_client_kwargs(
            headers=headers,
            cookies=cookies,
            trust_env=trust_env,
            proxy=proxy,
            timeout=timeout,
            http2=http2,
            verify=verify,
        )
    )
    return client


def create_sync_client(
    headers: dict[str, str] = DEFAULT_HEADERS,
    cookies: httpx.Cookies = DEFAULT_COOKIES,
    trust_env: bool = DEFAULT_TRUST_ENV,
    proxy: str | None = DEFAULT_PROXY,
    timeout: int | httpx.Timeout = 5,
    *,
    http2: bool = True,
    verify: bool = False,
) -> httpx.Client:
    client = httpx.Client(
        **_client_kwargs(
            headers=headers,
            cookies=cookies,
            trust_env=trust_env,
            proxy=proxy,
            timeout=timeout,
            http2=http2,
            verify=verify,
        )
    )
    return client
