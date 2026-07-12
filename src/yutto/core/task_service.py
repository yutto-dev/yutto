from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

from yutto.core.application import YuttoApplication
from yutto.core.operation import bind_operation_event_emitter
from yutto.core.request import DownloadRequest
from yutto.runtime import TaskRuntime

if TYPE_CHECKING:
    from collections.abc import Callable

    from yutto.runtime import EventReplay, TaskContext, TaskEvent, TaskSnapshot
    from yutto.utils.fetcher import FetcherContext


class DownloadApplication(Protocol):
    async def download(self, request: DownloadRequest) -> None: ...


class DownloadTaskService:
    """Run frontend-independent download requests through a single-worker runtime."""

    def __init__(
        self,
        context_factory: Callable[[DownloadRequest], FetcherContext],
        *,
        application_factory: Callable[[FetcherContext], DownloadApplication] = YuttoApplication,
        replay_limit: int = 100,
        task_limit: int = 256,
        task_id_factory: Callable[[], str] | None = None,
    ):
        self._context_factory = context_factory
        self._application_factory = application_factory
        self.runtime = TaskRuntime[DownloadRequest, None](
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

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, None]:
        return await self.runtime.submit(request)

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None:
        return self.runtime.get(task_id)

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, None], ...]:
        return self.runtime.list()

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None:
        return await self.runtime.cancel(task_id)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        return self.runtime.replay(task_id, after_seq=after_seq)

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        return self.runtime.add_event_listener(listener)

    async def _run(self, request: DownloadRequest, task_context: TaskContext) -> None:
        ctx = self._context_factory(request)
        application = self._application_factory(ctx)
        with bind_operation_event_emitter(task_context.emit):
            await application.download(request)
