from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import quote, unquote, urlparse

from returns.result import Failure, Result, Success
from typing_extensions import ParamSpec

from yutto._native import (
    HttpError,
    HttpTimeoutError,
    InvalidUrlError,
    SessionClosedError,
    UnsupportedProtocolError,
    YuttoSession,
)
from yutto.core.operation import ReportLevel, emit_download_report
from yutto.exceptions import MaxRetryError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine, Iterator, Mapping

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
                except SessionClosedError:
                    raise
                except HttpTimeoutError:
                    emit_download_report(
                        f"抓取超时，正在重试，剩余 {retry - 1} 次",
                        level=ReportLevel.WARNING,
                    )
                except (InvalidUrlError, UnsupportedProtocolError) as e:
                    raise e
                except HttpError as e:
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


class _FetchTrace:
    def __init__(self, operation: str, url: str):
        self.operation = operation
        self.url = url

    def complete(self, detail: str | None = None) -> None:
        suffix = f" ({detail})" if detail is not None else ""
        emit_download_report(f"{self.operation} completed: {self.url}{suffix}", level=ReportLevel.DEBUG)


@contextmanager
def trace_fetch(operation: str, url: str) -> Iterator[_FetchTrace]:
    emit_download_report(f"{operation} started: {url}", level=ReportLevel.DEBUG)
    trace = _FetchTrace(operation, url)
    try:
        yield trace
    except (asyncio.CancelledError, Exception) as error:
        error_detail = type(error).__name__
        if str(error):
            error_detail += f": {error}"
        emit_download_report(
            f"{operation} failed: {url} ({error_detail})",
            level=ReportLevel.DEBUG,
        )
        raise


def unwrap_fetch_result(result: Result[RetT, MaxRetryError]) -> RetT:
    match result:
        case Success(value):
            return value
        case Failure(error):
            raise error
    raise AssertionError("无法解析响应结果")


DEFAULT_PROXY = None
DEFAULT_TRUST_ENV = True
DEFAULT_FETCH_WORKERS = 8
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}
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


def cookies_from_auth(auth_info: AuthInfo | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if auth_info is None:
        return cookies
    # 先解码后编码是防止获取到的 SESSDATA 是已经解码后的（包含「,」）
    # 而番剧无法使用解码后的 SESSDATA
    cookies["SESSDATA"] = quote(unquote(auth_info["SESSDATA"]))
    if auth_info["bili_jct"]:
        cookies["bili_jct"] = auth_info["bili_jct"]
    return cookies


class Fetcher:
    @staticmethod
    @MaxRetry(2)
    async def fetch_text(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        encoding: str | None = None,
    ) -> str | None:
        async with scope.fetch_guard():
            with trace_fetch("Fetch text", url) as trace:
                resp = await scope.session.get(url, params=_query_params(params))
                if not resp.is_success:
                    trace.complete(f"HTTP {resp.status_code}")
                    return None
                body = resp.body
                trace.complete(f"HTTP {resp.status_code}, {len(body)} bytes")
                return body.decode(encoding or "utf-8", errors="replace")

    @staticmethod
    @MaxRetry(2)
    async def fetch_bin(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> bytes | None:
        async with scope.fetch_guard():
            with trace_fetch("Fetch bin", url) as trace:
                resp = await scope.session.get(url, params=_query_params(params))
                if not resp.is_success:
                    trace.complete(f"HTTP {resp.status_code}")
                    return None
                body = resp.body
                trace.complete(f"HTTP {resp.status_code}, {len(body)} bytes")
                return body

    @staticmethod
    @MaxRetry(2)
    async def fetch_json(
        scope: ExecutionScope,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        async with scope.fetch_guard():
            with trace_fetch("Fetch json", url) as trace:
                resp = await scope.session.get(url, params=_query_params(params))
                if not resp.is_success:
                    resp.raise_for_status()
                body = resp.body
                result = json.loads(body)
                trace.complete(f"HTTP {resp.status_code}, {len(body)} bytes")
                return result

    @staticmethod
    @MaxRetry(2)
    async def get_redirected_url(scope: ExecutionScope, url: str) -> str:
        # 关于为什么要前往重定向 url，是因为 B 站的 url 类型实在是太多了，比如有 b23.tv 的短链接
        # 为 SEO 的搜索引擎链接、甚至有的 av、BV 链接实际上是番剧页面，一一列举实在太麻烦，而且最后一种
        # 情况需要在 av、BV 解析一部分信息后才能知道是否是番剧页面，处理起来非常麻烦（bilili 就是这么做的）
        async with scope.fetch_guard():
            with trace_fetch("Fetch redirected url", url) as trace:
                resp = await scope.session.get(url)
                redirected_url = resp.url
                if redirected_url == url:
                    trace.complete(f"HTTP {resp.status_code}, unchanged")
                else:
                    trace.complete(f"HTTP {resp.status_code}, redirected to {redirected_url}")
                return redirected_url

    @staticmethod
    @MaxRetry(2)
    async def get_size(scope: ExecutionScope, url: str) -> int | None:
        async with scope.fetch_guard():
            with trace_fetch("Fetch size", url) as trace:
                size = await scope.session.probe_size(url)
                if size is not None:
                    trace.complete(f"{size} bytes")
                else:
                    trace.complete("size unknown")
                return size

    @staticmethod
    @MaxRetry(2)
    async def touch_url(scope: ExecutionScope, url: str) -> None:
        if url in scope.touched_urls:
            emit_download_report(f"Fetch touch skipped: {url} (cache hit)", level=ReportLevel.DEBUG)
            return
        async with scope.fetch_guard():
            with trace_fetch("Fetch touch", url) as trace:
                resp = await scope.session.get(url)
                scope.touched_urls.add(url)
                trace.complete(f"HTTP {resp.status_code}")


def _query_params(params: Mapping[str, Any] | None) -> list[tuple[str, str]] | None:
    if params is None:
        return None
    result = []
    for key, value in params.items():
        values = value if isinstance(value, (list, tuple)) else (value,)
        result.extend((str(key), _query_value(item)) for item in values)
    return result


def _query_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


@asynccontextmanager
async def create_client(
    headers: Mapping[str, str] | None = DEFAULT_HEADERS,
    cookies: Mapping[str, str] | None = None,
    trust_env: bool = DEFAULT_TRUST_ENV,
    proxy: str | None = DEFAULT_PROXY,
    timeout: float = 5,
    *,
    verify: bool = False,
) -> AsyncIterator[YuttoSession]:
    ca_cert_file = os.environ.get("SSL_CERT_FILE") if trust_env and verify else None
    ca_cert_dir = os.environ.get("SSL_CERT_DIR") if trust_env and verify and not ca_cert_file else None
    session = YuttoSession(
        headers=dict(headers or {}),
        cookies=dict(cookies or {}),
        proxy=proxy,
        use_system_proxy=trust_env,
        accept_invalid_certs=not verify,
        ca_cert_file=ca_cert_file,
        ca_cert_dir=ca_cert_dir,
        read_timeout=timeout,
        connect_timeout=timeout,
    )
    try:
        yield session
    finally:
        session.close()
