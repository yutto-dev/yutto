from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, get_type_hints

import pytest

from yutto.core.events import (
    DownloadArtifactCreated,
    DownloadBatchStarted,
    DownloadEventSink,
    DownloadItemListed,
    DownloadItemSkipped,
    DownloadProgress,
    DownloadRequestQueued,
    DownloadStage,
    DownloadStageChanged,
)
from yutto.core.execution import ExecutionScopeFactory, RequestExecutionScopeFactory
from yutto.core.operation import emit_download_event
from yutto.core.request import DownloadRequest
from yutto.core.result import DownloadResult, ItemSkipReason, ResolvedItem
from yutto.core.task_service import DownloadTaskService, _encode_runtime_event
from yutto.runtime import TaskState
from yutto.types import AId, CId
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
    def __init__(
        self,
        scope_factory: ExecutionScopeFactory,
        event_sink: DownloadEventSink,
        calls: list[tuple[ExecutionScopeFactory, str]],
    ):
        self.scope_factory = scope_factory
        self.event_sink = event_sink
        self.calls = calls
        self.result = DownloadResult()

    async def download(self, request: DownloadRequest) -> DownloadResult:
        self.event_sink.emit(DownloadStageChanged(name=DownloadStage.RESOLVING))
        self.calls.append((self.scope_factory, request.source.url))
        return self.result


@as_sync
async def test_download_task_service_runs_requests_in_order_and_bridges_events():
    ids = task_ids()
    scope_factory = RequestExecutionScopeFactory()
    calls: list[tuple[ExecutionScopeFactory, str]] = []

    def application_factory(
        factory: ExecutionScopeFactory,
        event_sink: DownloadEventSink,
    ) -> RecordingApplication:
        return RecordingApplication(factory, event_sink, calls)

    service = DownloadTaskService(
        scope_factory,
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
        assert first_done.result == DownloadResult()
        assert second_done.result == DownloadResult()
        assert [url for _, url in calls] == ["BV1first", "BV1second"]
        assert all(factory is scope_factory for factory, _ in calls)
        first_replay = service.replay(first.task_id)
        assert first_replay is not None
        assert [(event.kind, event.data) for event in first_replay.events if event.kind == "stage"] == [
            ("stage", {"name": "resolving"})
        ]


@as_sync
async def test_download_events_are_noop_outside_application_context():
    emit_download_event(DownloadProgress(current=1, total=2, speed_per_second=3.0))


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (DownloadBatchStarted(total=2), ("batch_started", {"total": 2})),
        (
            DownloadRequestQueued(url="BV1test", index=1, total=2),
            ("request_queued", {"url": "BV1test", "index": 1, "total": 2}),
        ),
        (
            DownloadStageChanged(name=DownloadStage.PREPARING, item="video"),
            ("stage", {"name": "preparing", "item": "video"}),
        ),
        (
            DownloadProgress(current=1, total=2, speed_per_second=3.0, buffered_blocks=2049),
            (
                "progress",
                {
                    "phase": "downloading",
                    "current": 1,
                    "total": 2,
                    "speed_per_second": 3.0,
                    "unit": "bytes",
                },
            ),
        ),
        (
            DownloadItemSkipped(item="video", reason=ItemSkipReason.ALREADY_EXISTS),
            ("item_skipped", {"item": "video", "reason": "already_exists"}),
        ),
        (
            DownloadArtifactCreated(item="video", path=Path("video.mp4")),
            ("artifact_created", {"path": "video.mp4", "item": "video"}),
        ),
    ],
)
def test_runtime_event_encoding_preserves_protocol(event, expected):
    assert _encode_runtime_event(event) == expected


def test_download_event_annotations_are_available_at_runtime():
    assert get_type_hints(DownloadArtifactCreated)["path"] is Path
    assert get_type_hints(DownloadItemSkipped)["reason"] is ItemSkipReason
    assert get_type_hints(DownloadItemListed)["item"] is ResolvedItem


def test_encode_runtime_event_item_listed_carries_full_wire_fields():
    item = ResolvedItem(
        avid=AId("1"),
        cid=CId("10"),
        url="https://www.bilibili.com/video/av1?p=1",
        name="P1",
        title="标题",
        cover_url="https://example.com/cover.jpg",
        planned_path=Path("标题/P1"),
        display_group="标题",
        uploader="某UP主",
        description="视频简介",
        tags=("标签A", "标签B"),
    )
    kind, data = _encode_runtime_event(DownloadItemListed(item=item))
    assert kind == "item_listed"
    assert data["avid"] == "1"
    assert data["cid"] == "10"
    assert data["planned_path"] == "标题/P1"
    assert data["tags"] == ["标签A", "标签B"]
