from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from yutto.utils.fetcher import (
    DEFAULT_FETCH_WORKERS,
    cookies_from_auth,
    create_client,
    resolve_proxy,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
    from contextlib import AbstractAsyncContextManager

    from httpx import AsyncClient

    from yutto.auth import AuthInfo
    from yutto.core.request import DownloadRequest
    from yutto.types import UserInfo


class ExecutionScope:
    """Runtime resources owned by one request execution."""

    client: AsyncClient
    fetch_limiter: asyncio.Semaphore
    download_limiter: asyncio.Semaphore
    user_info_cache: UserInfo | None
    wbi_img_cache: Mapping[str, str] | None
    touched_urls: set[str]

    def __init__(
        self,
        client: AsyncClient,
        *,
        fetch_workers: int = DEFAULT_FETCH_WORKERS,
        download_workers: int = DEFAULT_FETCH_WORKERS,
    ):
        self.client = client
        self.fetch_limiter = asyncio.Semaphore(fetch_workers)
        self.download_limiter = asyncio.Semaphore(download_workers)
        self.user_info_cache = None
        self.wbi_img_cache = None
        self.touched_urls = set()

    @asynccontextmanager
    async def fetch_guard(self):
        async with self.fetch_limiter:
            yield

    @asynccontextmanager
    async def download_guard(self):
        async with self.download_limiter:
            yield


class ExecutionScopeFactory(Protocol):
    """Open all runtime resources required by one request."""

    def open(self, request: DownloadRequest) -> AbstractAsyncContextManager[ExecutionScope]: ...


class RequestExecutionScopeFactory:
    """Build request-scoped clients, concurrency guards, credentials, and caches."""

    def __init__(
        self,
        credential_resolver: Callable[[DownloadRequest], AuthInfo | None] | None = None,
        *,
        on_open: Callable[[ExecutionScope, DownloadRequest], Awaitable[None]] | None = None,
    ):
        self._credential_resolver = credential_resolver or (lambda request: None)
        self._on_open = on_open

    @asynccontextmanager
    async def open(self, request: DownloadRequest) -> AsyncIterator[ExecutionScope]:
        proxy, trust_env = resolve_proxy(request.network.proxy)
        auth = self._credential_resolver(request)
        cookies = cookies_from_auth(auth)

        async with create_client(
            cookies=cookies,
            trust_env=trust_env,
            proxy=proxy,
        ) as client:
            scope = ExecutionScope(
                client,
                fetch_workers=request.network.fetch_workers,
                download_workers=request.network.download_workers,
            )
            if self._on_open is not None:
                await self._on_open(scope, request)
            yield scope
