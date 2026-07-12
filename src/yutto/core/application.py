from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from yutto.core.events import DownloadBatchStarted, DownloadRequestQueued, NullApplicationEventSink
from yutto.core.operation import emit_operation_event
from yutto.download_manager import DownloadManager, DownloadTask

if TYPE_CHECKING:
    from collections.abc import Sequence

    from yutto.core.events import ApplicationEventSink
    from yutto.core.request import DownloadRequest
    from yutto.utils.fetcher import FetcherContext


class DownloadQueue(Protocol):
    def start(self, ctx: FetcherContext) -> None: ...

    async def add_task(self, task: DownloadTask) -> None: ...

    async def add_stop_task(self) -> None: ...

    async def wait_for_completion(self) -> None: ...


class YuttoApplication:
    """Frontend-independent orchestration for one yutto invocation."""

    def __init__(
        self,
        ctx: FetcherContext,
        *,
        event_sink: ApplicationEventSink | None = None,
        manager: DownloadQueue | None = None,
    ):
        self.ctx = ctx
        self.event_sink = event_sink if event_sink is not None else NullApplicationEventSink()
        self.manager = manager if manager is not None else DownloadManager()

    async def download_all(self, requests: Sequence[DownloadRequest]) -> None:
        self.manager.start(self.ctx)
        total = len(requests)
        if total > 1:
            event = DownloadBatchStarted(total=total)
            self.event_sink.emit(event)
            emit_operation_event("batch_started", {"total": total})

        for index, request in enumerate(requests, start=1):
            if total > 1:
                event = DownloadRequestQueued(
                    url=request.source.url,
                    index=index,
                    total=total,
                )
                self.event_sink.emit(event)
                emit_operation_event(
                    "request_queued",
                    {"url": request.source.url, "index": index, "total": total},
                )
            await self.manager.add_task(DownloadTask(request=request))

        await self.manager.add_stop_task()
        await self.manager.wait_for_completion()

    async def download(self, request: DownloadRequest) -> None:
        await self.download_all([request])
