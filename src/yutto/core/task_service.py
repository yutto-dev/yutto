from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, assert_never

from yutto.core.events import (
    DownloadArtifactCreated,
    DownloadBatchStarted,
    DownloadEvent,
    DownloadEventSink,
    DownloadItemSkipped,
    DownloadProgress,
    DownloadRequestQueued,
    DownloadStageChanged,
)
from yutto.core.request import DownloadRequest
from yutto.core.result import DownloadResult
from yutto.runtime import TaskRuntime

if TYPE_CHECKING:
    from collections.abc import Callable

    from yutto.runtime import EventReplay, TaskContext, TaskEvent, TaskSnapshot
    from yutto.utils.fetcher import FetcherContext


class DownloadApplication(Protocol):
    async def download(self, request: DownloadRequest) -> DownloadResult: ...


class DownloadTaskService:
    """Run frontend-independent download requests through a single-worker runtime."""

    def __init__(
        self,
        context_factory: Callable[[DownloadRequest], FetcherContext],
        application_factory: Callable[[FetcherContext, DownloadEventSink], DownloadApplication],
        *,
        replay_limit: int = 100,
        task_limit: int = 256,
        task_id_factory: Callable[[], str] | None = None,
    ):
        self._context_factory = context_factory
        self._application_factory = application_factory
        self.runtime = TaskRuntime[DownloadRequest, DownloadResult](
            self._run,
            worker_count=1,
            replay_limit=replay_limit,
            task_limit=task_limit,
            task_id_factory=task_id_factory,
        )

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close(cancel_pending=True)

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self, *, cancel_pending: bool = False) -> None:
        await self.runtime.close(cancel_pending=cancel_pending)

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, DownloadResult]:
        return await self.runtime.submit(request)

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, DownloadResult] | None:
        return self.runtime.get(task_id)

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, DownloadResult], ...]:
        return self.runtime.list()

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, DownloadResult] | None:
        return await self.runtime.cancel(task_id)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        return self.runtime.replay(task_id, after_seq=after_seq)

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        return self.runtime.add_event_listener(listener)

    async def _run(self, request: DownloadRequest, task_context: TaskContext) -> DownloadResult:
        ctx = self._context_factory(request)
        application = self._application_factory(ctx, _RuntimeDownloadEventSink(task_context))
        return await application.download(request)


class _RuntimeDownloadEventSink:
    def __init__(self, task_context: TaskContext):
        self._task_context = task_context

    def emit(self, event: DownloadEvent) -> None:
        kind, data = _encode_runtime_event(event)
        self._task_context.emit(kind, data)


def _encode_runtime_event(event: DownloadEvent) -> tuple[str, dict[str, object]]:
    match event:
        case DownloadBatchStarted(total=total):
            return "batch_started", {"total": total}
        case DownloadRequestQueued(url=url, index=index, total=total):
            return "request_queued", {"url": url, "index": index, "total": total}
        case DownloadStageChanged(name=name, item=item):
            data: dict[str, object] = {"name": name.value}
            if item is not None:
                data["item"] = item
            return "stage", data
        case DownloadProgress(current=current, total=total, speed_per_second=speed, phase=phase, unit=unit):
            return "progress", {
                "phase": phase.value,
                "current": current,
                "total": total,
                "speed_per_second": speed,
                "unit": unit,
            }
        case DownloadItemSkipped(item=item, reason=reason):
            return "item_skipped", {"item": item, "reason": reason.value}
        case DownloadArtifactCreated(item=item, path=path):
            return "artifact_created", {"path": path.as_posix(), "item": item}
        case _ as unreachable:
            assert_never(unreachable)
