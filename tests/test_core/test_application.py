from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from yutto.core.application import YuttoApplication
from yutto.core.events import DownloadBatchStarted, DownloadRequestQueued
from yutto.core.request import DownloadRequest
from yutto.utils.fetcher import FetcherContext
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from yutto.core.events import ApplicationEvent
    from yutto.download_manager import DownloadTask

pytestmark = pytest.mark.processor


class RecordingEventSink:
    def __init__(self):
        self.events: list[ApplicationEvent] = []

    def emit(self, event: ApplicationEvent) -> None:
        self.events.append(event)


class RecordingManager:
    def __init__(self):
        self.actions: list[tuple[str, Any]] = []

    def start(self, ctx: FetcherContext) -> None:
        self.actions.append(("start", ctx))

    async def add_task(self, task: DownloadTask) -> None:
        self.actions.append(("task", task.request.source.url))

    async def add_stop_task(self) -> None:
        self.actions.append(("stop", None))

    async def wait_for_completion(self) -> None:
        self.actions.append(("wait", None))


def make_request(url: str) -> DownloadRequest:
    return DownloadRequest.model_validate({"source": {"url": url}})


@as_sync
async def test_application_preserves_queue_order_and_emits_batch_events():
    ctx = FetcherContext()
    manager = RecordingManager()
    sink = RecordingEventSink()
    requests = [make_request("BV1first"), make_request("BV1second")]

    application = YuttoApplication(ctx, event_sink=sink, manager=manager)
    await application.download_all(requests)

    assert manager.actions == [
        ("start", ctx),
        ("task", "BV1first"),
        ("task", "BV1second"),
        ("stop", None),
        ("wait", None),
    ]
    assert sink.events == [
        DownloadBatchStarted(total=2),
        DownloadRequestQueued(url="BV1first", index=1, total=2),
        DownloadRequestQueued(url="BV1second", index=2, total=2),
    ]


@as_sync
async def test_single_download_does_not_emit_batch_presentation_events():
    manager = RecordingManager()
    sink = RecordingEventSink()
    application = YuttoApplication(
        FetcherContext(),
        event_sink=sink,
        manager=manager,
    )

    await application.download(make_request("BV1single"))

    assert sink.events == []
    assert [action[0] for action in manager.actions] == ["start", "task", "stop", "wait"]
