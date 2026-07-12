from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from yutto.core.operation import emit_operation_event
from yutto.core.request import DownloadRequest
from yutto.core.task_service import DownloadTaskService
from yutto.runtime import TaskState
from yutto.utils.fetcher import FetcherContext
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.processor


def task_ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"download-{index}"


class RecordingApplication:
    def __init__(self, ctx: FetcherContext, calls: list[tuple[FetcherContext, str]]):
        self.ctx = ctx
        self.calls = calls

    async def download(self, request: DownloadRequest) -> None:
        emit_operation_event("stage", {"name": "resolving"})
        self.calls.append((self.ctx, request.source.url))


@as_sync
async def test_download_task_service_runs_requests_in_order_and_bridges_events():
    ids = task_ids()
    contexts: list[FetcherContext] = []
    calls: list[tuple[FetcherContext, str]] = []

    def context_factory(request: DownloadRequest) -> FetcherContext:
        ctx = FetcherContext()
        contexts.append(ctx)
        return ctx

    def application_factory(ctx: FetcherContext) -> RecordingApplication:
        return RecordingApplication(ctx, calls)

    service = DownloadTaskService(
        context_factory,
        application_factory=application_factory,
        task_id_factory=lambda: next(ids),
    )
    async with service:
        first = await service.submit(DownloadRequest.model_validate({"source": {"url": "BV1first"}}))
        second = await service.submit(DownloadRequest.model_validate({"source": {"url": "BV1second"}}))
        first_done = await service.runtime.wait(first.task_id)
        second_done = await service.runtime.wait(second.task_id)

        assert first_done is not None and second_done is not None
        assert first_done.state is TaskState.COMPLETED
        assert second_done.state is TaskState.COMPLETED
        assert [url for _, url in calls] == ["BV1first", "BV1second"]
        assert [ctx for ctx, _ in calls] == contexts
        first_replay = service.replay(first.task_id)
        assert first_replay is not None
        assert [(event.kind, event.data) for event in first_replay.events if event.kind == "stage"] == [
            ("stage", {"name": "resolving"})
        ]


@as_sync
async def test_operation_events_are_noop_outside_task_context():
    emit_operation_event("progress", {"current": 1})
