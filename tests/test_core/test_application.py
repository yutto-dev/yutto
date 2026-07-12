from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from yutto.core.application import YuttoApplication
from yutto.core.events import DownloadBatchStarted, DownloadRequestQueued, DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event
from yutto.core.request import DownloadRequest
from yutto.core.result import DownloadResult
from yutto.utils.fetcher import FetcherContext
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from collections.abc import Sequence

    from yutto.core.events import DownloadEvent

pytestmark = pytest.mark.processor


class RecordingEventSink:
    def __init__(self, trace: list[tuple[str, object]]):
        self.events: list[DownloadEvent] = []
        self.trace = trace

    def emit(self, event: DownloadEvent) -> None:
        self.events.append(event)
        self.trace.append(("event", event))


class RecordingWorkflow:
    def __init__(self, trace: list[tuple[str, object]]):
        self.trace = trace
        self.result = DownloadResult()

    async def execute(self, ctx: FetcherContext, requests: Sequence[DownloadRequest]) -> DownloadResult:
        self.trace.append(("execute", (ctx, tuple(requests))))
        emit_download_event(DownloadStageChanged(name=DownloadStage.RESOLVING))
        return self.result


def make_request(url: str) -> DownloadRequest:
    return DownloadRequest.model_validate({"source": {"url": url}})


@as_sync
async def test_application_preserves_queue_order_and_emits_batch_events():
    ctx = FetcherContext()
    trace: list[tuple[str, object]] = []
    workflow = RecordingWorkflow(trace)
    sink = RecordingEventSink(trace)
    requests = [make_request("BV1first"), make_request("BV1second")]

    application = YuttoApplication(ctx, workflow=workflow, event_sink=sink)
    result = await application.download_all(requests)

    assert trace == [
        ("event", DownloadBatchStarted(total=2)),
        ("event", DownloadRequestQueued(url="BV1first", index=1, total=2)),
        ("event", DownloadRequestQueued(url="BV1second", index=2, total=2)),
        ("execute", (ctx, tuple(requests))),
        ("event", DownloadStageChanged(name=DownloadStage.RESOLVING)),
    ]
    assert sink.events == [
        DownloadBatchStarted(total=2),
        DownloadRequestQueued(url="BV1first", index=1, total=2),
        DownloadRequestQueued(url="BV1second", index=2, total=2),
        DownloadStageChanged(name=DownloadStage.RESOLVING),
    ]
    assert result is workflow.result


@as_sync
async def test_single_download_does_not_emit_batch_presentation_events():
    trace: list[tuple[str, object]] = []
    workflow = RecordingWorkflow(trace)
    sink = RecordingEventSink(trace)
    ctx = FetcherContext()
    request = make_request("BV1single")
    application = YuttoApplication(
        ctx,
        workflow=workflow,
        event_sink=sink,
    )

    result = await application.download(request)

    assert sink.events == [DownloadStageChanged(name=DownloadStage.RESOLVING)]
    assert trace == [
        ("execute", (ctx, (request,))),
        ("event", DownloadStageChanged(name=DownloadStage.RESOLVING)),
    ]
    assert result is workflow.result
