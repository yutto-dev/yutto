from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from yutto.core.events import DownloadBatchStarted, DownloadRequestQueued, NullDownloadEventSink
from yutto.core.operation import bind_download_event_sink, emit_download_event

if TYPE_CHECKING:
    from collections.abc import Sequence

    from yutto.core.events import DownloadEventSink
    from yutto.core.request import DownloadRequest
    from yutto.core.result import DownloadResult
    from yutto.utils.fetcher import FetcherContext


class DownloadWorkflow(Protocol):
    async def execute(self, ctx: FetcherContext, requests: Sequence[DownloadRequest]) -> DownloadResult: ...


class YuttoApplication:
    """Frontend-independent orchestration for one yutto invocation."""

    def __init__(
        self,
        ctx: FetcherContext,
        *,
        workflow: DownloadWorkflow,
        event_sink: DownloadEventSink | None = None,
    ):
        self.ctx = ctx
        self.workflow = workflow
        self.event_sink = event_sink if event_sink is not None else NullDownloadEventSink()

    async def download_all(self, requests: Sequence[DownloadRequest]) -> DownloadResult:
        with bind_download_event_sink(self.event_sink):
            total = len(requests)
            if total > 1:
                emit_download_event(DownloadBatchStarted(total=total))

            for index, request in enumerate(requests, start=1):
                if total > 1:
                    emit_download_event(
                        DownloadRequestQueued(
                            url=request.source.url,
                            index=index,
                            total=total,
                        )
                    )
            return await self.workflow.execute(self.ctx, requests)

    async def download(self, request: DownloadRequest) -> DownloadResult:
        return await self.download_all([request])
