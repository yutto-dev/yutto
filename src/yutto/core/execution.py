from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from yutto.utils.fetcher import ExecutionScope, cookies_from_auth, create_client, resolve_proxy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from contextlib import AbstractAsyncContextManager

    from yutto.auth import AuthInfo
    from yutto.core.request import DownloadRequest


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
                proxy=proxy,
                trust_env=trust_env,
                cookies=cookies,
                fetch_workers=request.network.fetch_workers,
                download_workers=request.network.download_workers,
            )
            if self._on_open is not None:
                await self._on_open(scope, request)
            yield scope
