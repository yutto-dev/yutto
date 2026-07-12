from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest

from yutto.exceptions import WrongUrlError
from yutto.runtime import RuntimeState, TaskCapacityError, TaskContext, TaskRuntime, TaskState
from yutto.utils.asynclib import first_successful
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor

if TYPE_CHECKING:
    from collections.abc import Iterator


def task_ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"task-{index}"


@pytest.mark.processor
@as_sync
async def test_runtime_lifecycle_completion_and_structured_events():
    ids = task_ids()

    async def handler(payload: str, context: TaskContext) -> str:
        context.emit("progress", {"current": 1, "total": 1})
        await asyncio.sleep(0)
        return payload.upper()

    runtime = TaskRuntime(handler, task_id_factory=lambda: next(ids))
    with pytest.raises(RuntimeError, match="not accepting"):
        await runtime.submit("before-start")

    await runtime.start()
    queued = await runtime.submit("video")
    assert queued.task_id == "task-1"
    assert queued.state is TaskState.QUEUED

    completed = await runtime.wait(queued.task_id)
    assert completed is not None
    assert completed.state is TaskState.COMPLETED
    assert completed.result == "VIDEO"
    assert completed.error is None
    assert completed.started_at is not None
    assert completed.finished_at is not None
    assert runtime.get(queued.task_id) == completed
    assert runtime.list() == (completed,)

    replay = runtime.replay(queued.task_id)
    assert replay is not None
    assert replay.truncated is False
    assert [(event.kind, event.state, event.data) for event in replay.events] == [
        ("state", TaskState.QUEUED, {"from": None, "to": "queued"}),
        ("state", TaskState.RUNNING, {"from": "queued", "to": "running"}),
        ("progress", TaskState.RUNNING, {"current": 1, "total": 1}),
        ("state", TaskState.COMPLETED, {"from": "running", "to": "completed"}),
    ]
    assert [event.seq for event in replay.events] == [1, 2, 3, 4]

    await runtime.close()
    assert runtime.state is RuntimeState.CLOSED
    await runtime.close()
    with pytest.raises(RuntimeError, match="not accepting"):
        await runtime.submit("after-close")


@pytest.mark.processor
@as_sync
async def test_event_sequence_is_global_and_replay_is_bounded():
    ids = task_ids()

    async def handler(payload: int, context: TaskContext) -> int:
        for current in range(4):
            context.emit("progress", {"current": current})
        return payload * 2

    async with TaskRuntime(handler, replay_limit=3, task_id_factory=lambda: next(ids)) as runtime:
        first = await runtime.submit(1)
        first_done = await runtime.wait(first.task_id)
        second = await runtime.submit(2)
        second_done = await runtime.wait(second.task_id)

        assert first_done is not None and second_done is not None
        assert first_done.last_event_seq < second_done.last_event_seq

        first_replay = runtime.replay(first.task_id)
        second_replay = runtime.replay(second.task_id)
        assert first_replay is not None and second_replay is not None
        assert first_replay.truncated is True
        assert second_replay.truncated is True
        assert len(first_replay.events) == len(second_replay.events) == runtime.replay_limit
        retained_sequences = [event.seq for event in (*first_replay.events, *second_replay.events)]
        assert retained_sequences == sorted(retained_sequences)
        assert len(retained_sequences) == len(set(retained_sequences))

        resumed = runtime.replay(first.task_id, after_seq=first_replay.events[-2].seq)
        assert resumed is not None
        assert resumed.truncated is False
        assert resumed.events == (first_replay.events[-1],)


@pytest.mark.processor
@as_sync
async def test_register_then_replay_handoff_does_not_lose_live_events():
    ready = asyncio.Event()
    release = asyncio.Event()

    async def handler(payload: str, context: TaskContext) -> str:
        context.emit("progress", {"step": "before-listener"})
        ready.set()
        await release.wait()
        context.emit("progress", {"step": "after-listener"})
        return payload

    async with TaskRuntime(handler) as runtime:
        submitted = await runtime.submit("video")
        await ready.wait()

        live_events = []
        unsubscribe = runtime.add_event_listener(live_events.append)
        release.set()
        completed = await runtime.wait(submitted.task_id)
        assert completed is not None

        replay = runtime.replay(submitted.task_id, after_seq=0)
        assert replay is not None
        unsubscribe()

        # Events emitted between listener registration and replay are intentionally
        # present in both sources. Sequence-based deduplication closes that race.
        assert {event.seq for event in live_events} & {event.seq for event in replay.events}
        merged = {event.seq: event for event in (*replay.events, *live_events)}
        ordered = [merged[seq] for seq in sorted(merged)]
        assert [event.seq for event in ordered] == list(range(1, completed.last_event_seq + 1))
        assert [event.data.get("step") for event in ordered if event.kind == "progress"] == [
            "before-listener",
            "after-listener",
        ]
        assert ordered[-1].state is TaskState.COMPLETED


@pytest.mark.processor
@as_sync
async def test_listener_failure_is_isolated_from_tasks_and_other_listeners():
    received = []

    async def handler(payload: str, context: TaskContext) -> str:
        context.emit("progress", {"payload": payload})
        return payload

    async with TaskRuntime(handler) as runtime:

        def broken_listener(event):
            raise RuntimeError(f"cannot handle {event.seq}")

        runtime.add_event_listener(broken_listener)
        runtime.add_event_listener(received.append)
        submitted = await runtime.submit("video")
        completed = await runtime.wait(submitted.task_id)

        assert completed is not None
        assert completed.state is TaskState.COMPLETED
        assert [event.kind for event in received] == ["state", "state", "progress", "state"]
        assert received[-1].state is TaskState.COMPLETED


@pytest.mark.processor
@as_sync
async def test_event_listener_unsubscribe_is_idempotent():
    received = []

    async def handler(payload: str, context: TaskContext) -> str:
        return payload

    async with TaskRuntime(handler) as runtime:
        unsubscribe = runtime.add_event_listener(received.append)
        first = await runtime.submit("first")
        assert await runtime.wait(first.task_id) is not None

        unsubscribe()
        unsubscribe()
        second = await runtime.submit("second")
        assert await runtime.wait(second.task_id) is not None

        assert received
        assert {event.task_id for event in received} == {first.task_id}


@pytest.mark.processor
@as_sync
async def test_failure_is_structured():
    async def handler(payload: str, context: TaskContext) -> None:
        raise ValueError(f"cannot process {payload}")

    async with TaskRuntime(handler, task_id_factory=lambda: "failed-task") as runtime:
        submitted = await runtime.submit("broken")
        failed = await runtime.wait(submitted.task_id)

        assert failed is not None
        assert failed.state is TaskState.FAILED
        assert failed.result is None
        assert failed.error is not None
        assert failed.error.type == "ValueError"
        assert failed.error.message == "cannot process broken"
        assert failed.error.code == "internal_error"

        replay = runtime.replay(submitted.task_id)
        assert replay is not None
        assert [event.state for event in replay.events if event.kind == "state"] == [
            TaskState.QUEUED,
            TaskState.RUNNING,
            TaskState.FAILED,
        ]
        assert replay.events[-1].data["error"] == {
            "code": "internal_error",
            "type": "ValueError",
            "message": "cannot process broken",
        }


@pytest.mark.processor
@as_sync
async def test_failure_messages_are_bounded():
    async def handler(payload: str, context: TaskContext) -> None:
        raise ValueError(payload)

    async with TaskRuntime(handler) as runtime:
        submitted = await runtime.submit("x" * 20_000)
        failed = await runtime.wait(submitted.task_id)

        assert failed is not None and failed.error is not None
        assert failed.error.truncated is True
        assert len(failed.error.message) == 16 * 1024 + 1
        replay = runtime.replay(submitted.task_id)
        assert replay is not None
        error_data = replay.events[-1].data["error"]
        assert isinstance(error_data, dict)
        assert cast("dict[str, object]", error_data)["truncated"] is True


@pytest.mark.processor
@as_sync
async def test_domain_failure_keeps_stable_yutto_error_code():
    async def handler(payload: str, context: TaskContext) -> None:
        raise WrongUrlError(payload)

    async with TaskRuntime(handler) as runtime:
        submitted = await runtime.submit("bad url")
        failed = await runtime.wait(submitted.task_id)

        assert failed is not None and failed.error is not None
        assert failed.error.code == 14


@pytest.mark.processor
@as_sync
async def test_cancel_is_idempotent_for_queued_and_running_tasks():
    ids = task_ids()
    first_started = asyncio.Event()
    block_first = asyncio.Event()

    async def handler(payload: str, context: TaskContext) -> str:
        if payload == "first":
            first_started.set()
            await block_first.wait()
        return payload

    runtime = TaskRuntime(handler, task_id_factory=lambda: next(ids))
    await runtime.start()
    first = await runtime.submit("first")
    await first_started.wait()
    second = await runtime.submit("second")

    second_cancelled = await runtime.cancel(second.task_id)
    assert second_cancelled is not None
    assert second_cancelled.state is TaskState.CANCELLED
    second_last_seq = second_cancelled.last_event_seq
    assert await runtime.cancel(second.task_id) == second_cancelled
    second_snapshot = runtime.get(second.task_id)
    assert second_snapshot is not None
    assert second_snapshot.last_event_seq == second_last_seq

    first_cancelling = await runtime.cancel(first.task_id)
    assert first_cancelling is not None
    assert first_cancelling.state is TaskState.CANCELLING
    first_last_seq = first_cancelling.last_event_seq
    assert await runtime.cancel(first.task_id) == first_cancelling
    first_snapshot = runtime.get(first.task_id)
    assert first_snapshot is not None
    assert first_snapshot.last_event_seq == first_last_seq

    first_cancelled = await runtime.wait(first.task_id)
    assert first_cancelled is not None
    assert first_cancelled.state is TaskState.CANCELLED
    assert first_cancelled.error is None

    for task_id in (first.task_id, second.task_id):
        replay = runtime.replay(task_id)
        assert replay is not None
        states = [event.state for event in replay.events if event.kind == "state"]
        assert TaskState.FAILED not in states
        assert states[-2:] == [TaskState.CANCELLING, TaskState.CANCELLED]

    await runtime.close()


@pytest.mark.processor
@as_sync
async def test_worker_count_allows_bounded_concurrency():
    running = 0
    max_running = 0
    both_started = asyncio.Event()
    release = asyncio.Event()

    async def handler(payload: int, context: TaskContext) -> int:
        nonlocal max_running, running
        running += 1
        max_running = max(max_running, running)
        if running == 2:
            both_started.set()
        try:
            await release.wait()
        finally:
            running -= 1
        return payload

    async with TaskRuntime(handler, worker_count=2) as runtime:
        first = await runtime.submit(1)
        second = await runtime.submit(2)
        await both_started.wait()
        assert runtime.worker_count == 2
        assert max_running == 2
        release.set()
        first_completed = await runtime.wait(first.task_id)
        second_completed = await runtime.wait(second.task_id)
        assert first_completed is not None and second_completed is not None
        assert first_completed.state is TaskState.COMPLETED
        assert second_completed.state is TaskState.COMPLETED


@pytest.mark.processor
@as_sync
async def test_close_can_cancel_running_and_queued_tasks():
    started = asyncio.Event()
    never_release = asyncio.Event()

    async def handler(payload: str, context: TaskContext) -> str:
        started.set()
        await never_release.wait()
        return payload

    runtime = TaskRuntime(handler)
    await runtime.start()
    running = await runtime.submit("running")
    await started.wait()
    queued = await runtime.submit("queued")

    await runtime.close(cancel_pending=True)

    assert runtime.state is RuntimeState.CLOSED
    running_snapshot = runtime.get(running.task_id)
    queued_snapshot = runtime.get(queued.task_id)
    assert running_snapshot is not None and queued_snapshot is not None
    assert running_snapshot.state is TaskState.CANCELLED
    assert queued_snapshot.state is TaskState.CANCELLED
    assert running_snapshot.error is None and queued_snapshot.error is None


@as_sync
async def test_runtime_cancellation_reaps_nested_first_successful_tasks():
    child_started = asyncio.Event()
    child_cancelled = asyncio.Event()

    async def child() -> None:
        child_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            child_cancelled.set()

    async def handler(payload: None, context: TaskContext) -> None:
        await first_successful([child()])

    async with TaskRuntime(handler) as runtime:
        submitted = await runtime.submit(None)
        await child_started.wait()
        await runtime.cancel(submitted.task_id)
        cancelled = await runtime.wait(submitted.task_id)

    assert cancelled is not None
    assert cancelled.state is TaskState.CANCELLED
    assert child_cancelled.is_set()


def test_runtime_rejects_invalid_limits():
    async def handler(payload: object, context: TaskContext) -> None:
        return None

    with pytest.raises(ValueError, match="worker_count"):
        TaskRuntime(handler, worker_count=0)
    with pytest.raises(ValueError, match="replay_limit"):
        TaskRuntime(handler, replay_limit=0)
    with pytest.raises(ValueError, match="task_limit"):
        TaskRuntime(handler, task_limit=0)


@pytest.mark.processor
@as_sync
async def test_task_history_is_bounded_and_only_terminal_tasks_are_evicted():
    ids = task_ids()

    async def complete(payload: str, context: TaskContext) -> str:
        return payload

    async with TaskRuntime(complete, task_limit=2, task_id_factory=lambda: next(ids)) as runtime:
        first = await runtime.submit("first")
        await runtime.wait(first.task_id)
        second = await runtime.submit("second")
        await runtime.wait(second.task_id)
        third = await runtime.submit("third")

        assert runtime.get(first.task_id) is None
        assert [snapshot.task_id for snapshot in runtime.list()] == [second.task_id, third.task_id]

    started = asyncio.Event()
    release = asyncio.Event()

    async def block(payload: str, context: TaskContext) -> str:
        started.set()
        await release.wait()
        return payload

    runtime = TaskRuntime(block, task_limit=1)
    await runtime.start()
    await runtime.submit("running")
    await started.wait()
    with pytest.raises(TaskCapacityError, match="capacity"):
        await runtime.submit("cannot-queue")
    await runtime.close(cancel_pending=True)


@pytest.mark.processor
@as_sync
async def test_evicted_cancelled_queue_entry_does_not_stop_worker():
    ids = task_ids()

    async def complete(payload: str, context: TaskContext) -> str:
        return payload

    async with TaskRuntime(complete, task_limit=1, task_id_factory=lambda: next(ids)) as runtime:
        cancelled = await runtime.submit("cancelled-before-worker")
        await runtime.cancel(cancelled.task_id)
        replacement = await runtime.submit("replacement")

        completed = await runtime.wait(replacement.task_id)
        assert completed is not None
        assert completed.state is TaskState.COMPLETED
        assert completed.result == "replacement"
