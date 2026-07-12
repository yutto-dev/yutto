from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from types import TracebackType


PayloadT = TypeVar("PayloadT")
ResultT = TypeVar("ResultT")
_MAX_ERROR_MESSAGE_LENGTH = 16 * 1024


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}


class RuntimeState(StrEnum):
    NEW = "new"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


class TaskCapacityError(RuntimeError):
    """The bounded runtime cannot retain another non-terminal task."""


@dataclass(frozen=True, slots=True)
class TaskError:
    type: str
    message: str
    code: int | str = "internal_error"
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: str
    seq: int
    kind: str
    state: TaskState
    created_at: datetime
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class EventReplay:
    task_id: str
    after_seq: int
    events: tuple[TaskEvent, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class TaskSnapshot(Generic[PayloadT, ResultT]):
    task_id: str
    state: TaskState
    payload: PayloadT
    result: ResultT | None
    error: TaskError | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    last_event_seq: int


@dataclass(slots=True)
class _TaskRecord(Generic[PayloadT, ResultT]):
    task_id: str
    state: TaskState
    payload: PayloadT
    result: ResultT | None
    error: TaskError | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    events: deque[TaskEvent]
    done: asyncio.Event
    dropped_through_seq: int = 0
    execution: asyncio.Task[ResultT] | None = None


_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({TaskState.RUNNING, TaskState.CANCELLING}),
    TaskState.RUNNING: frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLING}),
    TaskState.CANCELLING: frozenset({TaskState.CANCELLED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}
_STOP = object()
_COALESCED_EVENT_KINDS = frozenset({"progress"})


class _TaskContextRuntime(Protocol):
    def _is_cancel_requested(self, task_id: str) -> bool: ...

    def _emit_custom(self, task_id: str, kind: str, data: Mapping[str, object] | None) -> TaskEvent: ...


class TaskContext:
    """A running task's handle for emitting structured, replayable events."""

    def __init__(self, runtime: _TaskContextRuntime, task_id: str):
        self._runtime = runtime
        self.task_id = task_id

    @property
    def cancel_requested(self) -> bool:
        return self._runtime._is_cancel_requested(self.task_id)

    def emit(self, kind: str, data: Mapping[str, object] | None = None) -> TaskEvent:
        """Emit an application event. ``state`` is reserved for runtime transitions."""
        return self._runtime._emit_custom(self.task_id, kind, data)


class TaskRuntime(Generic[PayloadT, ResultT]):
    """Run awaitable jobs in-process with bounded event replay.

    The runtime is bound to the event loop where :meth:`start` is called. Submitters
    must explicitly start it before accepting jobs and close it when finished. By
    default one worker processes jobs in submission order; ``worker_count`` can be
    increased when callers are ready for concurrent execution.
    """

    def __init__(
        self,
        handler: Callable[[PayloadT, TaskContext], Awaitable[ResultT]],
        *,
        worker_count: int = 1,
        replay_limit: int = 100,
        task_limit: int = 256,
        task_id_factory: Callable[[], str] | None = None,
    ):
        if worker_count < 1:
            raise ValueError("worker_count must be at least 1")
        if replay_limit < 1:
            raise ValueError("replay_limit must be at least 1")
        if task_limit < 1:
            raise ValueError("task_limit must be at least 1")

        self._handler = handler
        self._worker_count = worker_count
        self._replay_limit = replay_limit
        self._task_limit = task_limit
        self._task_id_factory = task_id_factory or (lambda: uuid4().hex)
        self._state = RuntimeState.NEW
        self._queue: asyncio.Queue[_TaskRecord[PayloadT, ResultT] | object] = asyncio.Queue()
        self._records: dict[str, _TaskRecord[PayloadT, ResultT]] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._next_seq = 1
        self._closed = asyncio.Event()
        self._event_listeners: dict[int, Callable[[TaskEvent], None]] = {}
        self._next_listener_id = 1

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def worker_count(self) -> int:
        return self._worker_count

    @property
    def replay_limit(self) -> int:
        return self._replay_limit

    @property
    def task_limit(self) -> int:
        return self._task_limit

    async def __aenter__(self) -> TaskRuntime[PayloadT, ResultT]:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close(cancel_pending=exc_type is not None)

    async def start(self) -> TaskRuntime[PayloadT, ResultT]:
        if self._state is RuntimeState.RUNNING:
            return self
        if self._state is not RuntimeState.NEW:
            raise RuntimeError(f"cannot start a runtime in {self._state} state")

        self._state = RuntimeState.RUNNING
        self._workers = [
            asyncio.create_task(self._worker_loop(), name=f"yutto-task-worker-{index}")
            for index in range(self._worker_count)
        ]
        return self

    async def close(self, *, cancel_pending: bool = False) -> None:
        """Stop accepting tasks and close workers.

        The default is graceful: queued and running jobs are allowed to finish.
        ``cancel_pending=True`` requests cancellation for every non-terminal task
        before waiting for workers to exit. Repeated calls are safe.
        """
        if self._state is RuntimeState.CLOSED:
            return
        if self._state is RuntimeState.NEW:
            self._state = RuntimeState.CLOSED
            self._closed.set()
            return
        if self._state is RuntimeState.CLOSING:
            await self._closed.wait()
            return

        self._state = RuntimeState.CLOSING
        try:
            if cancel_pending:
                for task_id in tuple(self._records):
                    await self.cancel(task_id)

            await self._wait_for_queue_or_worker_failure()
            for _ in self._workers:
                self._queue.put_nowait(_STOP)
            await asyncio.gather(*self._workers)
        except BaseException:
            for worker in self._workers:
                worker.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
            raise
        finally:
            self._workers.clear()
            self._state = RuntimeState.CLOSED
            self._closed.set()

    async def _wait_for_queue_or_worker_failure(self) -> None:
        queue_join = asyncio.create_task(self._queue.join(), name="yutto-task-queue-join")
        try:
            await asyncio.wait([queue_join, *self._workers], return_when=asyncio.FIRST_COMPLETED)
            failed_worker = next((worker for worker in self._workers if worker.done()), None)
            if failed_worker is None:
                await queue_join
                return

            error = RuntimeError(f"task runtime worker exited unexpectedly: {failed_worker.get_name()}")
            if failed_worker.cancelled():
                raise error from asyncio.CancelledError()
            failure = failed_worker.exception()
            if failure is not None:
                raise error from failure
            raise error
        finally:
            if not queue_join.done():
                queue_join.cancel()
            await asyncio.gather(queue_join, return_exceptions=True)

    async def submit(self, payload: PayloadT) -> TaskSnapshot[PayloadT, ResultT]:
        if self._state is not RuntimeState.RUNNING:
            raise RuntimeError("task runtime is not accepting submissions")

        task_id = self._task_id_factory()
        if not task_id:
            raise ValueError("task_id_factory returned an empty task id")
        if task_id in self._records:
            raise ValueError(f"duplicate task id: {task_id}")

        self._make_task_slot()

        created_at = datetime.now(UTC)
        record = _TaskRecord[PayloadT, ResultT](
            task_id=task_id,
            state=TaskState.QUEUED,
            payload=payload,
            result=None,
            error=None,
            created_at=created_at,
            started_at=None,
            finished_at=None,
            events=deque(maxlen=self._replay_limit),
            done=asyncio.Event(),
        )
        self._records[task_id] = record
        self._emit_state(record, previous=None)
        self._queue.put_nowait(record)
        return self._snapshot(record)

    def _make_task_slot(self) -> None:
        while len(self._records) >= self._task_limit:
            terminal_task_id = next(
                (task_id for task_id, record in self._records.items() if record.state.is_terminal),
                None,
            )
            if terminal_task_id is None:
                raise TaskCapacityError("task runtime capacity reached")
            del self._records[terminal_task_id]

    def get(self, task_id: str) -> TaskSnapshot[PayloadT, ResultT] | None:
        record = self._records.get(task_id)
        return self._snapshot(record) if record is not None else None

    def list(self) -> tuple[TaskSnapshot[PayloadT, ResultT], ...]:
        return tuple(self._snapshot(record) for record in self._records.values())

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        """Register a synchronous listener and return an idempotent unsubscribe.

        For a gap-free replay-to-live handoff, register the listener first, then
        call :meth:`replay` with the last observed sequence and deduplicate the
        combined events by ``seq``. Events are retained before listeners run, so
        an event racing with replay can be observed twice but cannot be missed.

        Listeners run inline and should remain lightweight. An exception from one
        listener is isolated from the task and from the remaining listeners.
        """
        listener_id = self._next_listener_id
        self._next_listener_id += 1
        self._event_listeners[listener_id] = listener
        subscribed = True

        def unsubscribe() -> None:
            nonlocal subscribed
            if not subscribed:
                return
            subscribed = False
            self._event_listeners.pop(listener_id, None)

        return unsubscribe

    async def wait(self, task_id: str) -> TaskSnapshot[PayloadT, ResultT] | None:
        record = self._records.get(task_id)
        if record is None:
            return None
        await record.done.wait()
        return self._snapshot(record)

    async def cancel(self, task_id: str) -> TaskSnapshot[PayloadT, ResultT] | None:
        """Request cancellation without converting cancellation into failure."""
        record = self._records.get(task_id)
        if record is None:
            return None
        if record.state.is_terminal or record.state is TaskState.CANCELLING:
            return self._snapshot(record)

        self._transition(record, TaskState.CANCELLING)
        if record.execution is None:
            self._transition(record, TaskState.CANCELLED)
        else:
            record.execution.cancel()
        return self._snapshot(record)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        if after_seq < 0:
            raise ValueError("after_seq must not be negative")
        record = self._records.get(task_id)
        if record is None:
            return None
        return EventReplay(
            task_id=task_id,
            after_seq=after_seq,
            events=tuple(event for event in record.events if event.seq > after_seq),
            truncated=record.dropped_through_seq > after_seq,
        )

    def _snapshot(self, record: _TaskRecord[PayloadT, ResultT]) -> TaskSnapshot[PayloadT, ResultT]:
        return TaskSnapshot(
            task_id=record.task_id,
            state=record.state,
            payload=record.payload,
            result=record.result,
            error=record.error,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            last_event_seq=record.events[-1].seq,
        )

    def _is_cancel_requested(self, task_id: str) -> bool:
        record = self._records.get(task_id)
        return record is not None and record.state in {TaskState.CANCELLING, TaskState.CANCELLED}

    def _emit_custom(self, task_id: str, kind: str, data: Mapping[str, object] | None) -> TaskEvent:
        if not kind:
            raise ValueError("event kind must not be empty")
        if kind == "state":
            raise ValueError("event kind 'state' is reserved")

        record = self._records[task_id]
        if record.state.is_terminal:
            raise RuntimeError("cannot emit events for a terminal task")
        return self._append_event(record, kind, dict(data or {}))

    def _emit_state(self, record: _TaskRecord[PayloadT, ResultT], previous: TaskState | None) -> TaskEvent:
        data: dict[str, object] = {
            "from": previous.value if previous is not None else None,
            "to": record.state.value,
        }
        if record.state is TaskState.FAILED and record.error is not None:
            error: dict[str, object] = {
                "code": record.error.code,
                "type": record.error.type,
                "message": record.error.message,
            }
            if record.error.truncated:
                error["truncated"] = True
            data["error"] = error
        return self._append_event(record, "state", data)

    def _append_event(
        self,
        record: _TaskRecord[PayloadT, ResultT],
        kind: str,
        data: dict[str, object],
    ) -> TaskEvent:
        if kind in _COALESCED_EVENT_KINDS:
            for retained_event in tuple(record.events):
                if retained_event.kind == kind:
                    record.events.remove(retained_event)
        if len(record.events) == self._replay_limit:
            record.dropped_through_seq = record.events[0].seq
        event = TaskEvent(
            task_id=record.task_id,
            seq=self._next_seq,
            kind=kind,
            state=record.state,
            created_at=datetime.now(UTC),
            data=data,
        )
        self._next_seq += 1
        record.events.append(event)
        for listener in tuple(self._event_listeners.values()):
            try:
                listener(event)
            except (Exception, asyncio.CancelledError):
                # Observers must never change the outcome of the task they observe.
                continue
        return event

    def _transition(self, record: _TaskRecord[PayloadT, ResultT], state: TaskState) -> None:
        previous = record.state
        if state not in _ALLOWED_TRANSITIONS[previous]:
            raise RuntimeError(f"invalid task transition: {previous} -> {state}")

        now = datetime.now(UTC)
        record.state = state
        if state is TaskState.RUNNING:
            record.started_at = now
        if state.is_terminal:
            record.finished_at = now
        self._emit_state(record, previous)
        if state.is_terminal:
            record.done.set()

    async def _execute(self, record: _TaskRecord[PayloadT, ResultT], context: TaskContext) -> ResultT:
        return await self._handler(record.payload, context)

    async def _worker_loop(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is _STOP:
                    return
                assert isinstance(item, _TaskRecord)
                record = item
                # A queued task may have been cancelled and then evicted from
                # bounded history before a worker reaches its queue entry.
                if self._records.get(record.task_id) is not record:
                    continue
                if record.state.is_terminal:
                    continue

                self._transition(record, TaskState.RUNNING)
                context = TaskContext(self, record.task_id)
                execution = asyncio.create_task(
                    self._execute(record, context),
                    name=f"yutto-task-{record.task_id}",
                )
                record.execution = execution
                try:
                    result = await execution
                except asyncio.CancelledError:
                    if record.state is not TaskState.CANCELLING:
                        self._transition(record, TaskState.CANCELLING)
                    self._transition(record, TaskState.CANCELLED)
                except Exception as error:
                    if record.state is TaskState.CANCELLING:
                        self._transition(record, TaskState.CANCELLED)
                    else:
                        message = str(error)
                        truncated = len(message) > _MAX_ERROR_MESSAGE_LENGTH
                        if truncated:
                            message = message[:_MAX_ERROR_MESSAGE_LENGTH] + "…"
                        error_code = getattr(getattr(error, "code", None), "value", "internal_error")
                        if not isinstance(error_code, (int, str)):
                            error_code = "internal_error"
                        record.error = TaskError(
                            type=type(error).__name__,
                            message=message,
                            code=error_code,
                            truncated=truncated,
                        )
                        self._transition(record, TaskState.FAILED)
                else:
                    if record.state is TaskState.CANCELLING:
                        self._transition(record, TaskState.CANCELLED)
                    else:
                        record.result = result
                        self._transition(record, TaskState.COMPLETED)
                finally:
                    record.execution = None
            finally:
                self._queue.task_done()
