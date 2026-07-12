from __future__ import annotations

import asyncio

import pytest

from yutto.downloader.downloader import _run_download_lifecycle
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


class FakeBuffer:
    def __init__(self, *, unflushed: bool = False) -> None:
        self.closed = False
        self.unflushed = unflushed
        self.ensure_flushed_calls = 0

    def ensure_flushed(self) -> None:
        self.ensure_flushed_calls += 1
        if self.unflushed:
            raise RuntimeError("buffer 尚未清空")

    async def close(self) -> None:
        self.closed = True


@pytest.mark.processor
@as_sync
async def test_download_lifecycle_failure_cancels_siblings_and_closes_buffers():
    progress_started = asyncio.Event()
    progress_cancelled = asyncio.Event()
    sibling_started = asyncio.Event()
    sibling_cancelled = asyncio.Event()
    buffer = FakeBuffer()

    async def progress():
        progress_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            progress_cancelled.set()

    async def failing_block():
        await progress_started.wait()
        await sibling_started.wait()
        raise RuntimeError("block failed")

    async def sibling_block():
        sibling_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            sibling_cancelled.set()

    with pytest.raises(RuntimeError, match="block failed"):
        await _run_download_lifecycle([progress(), failing_block(), sibling_block()], [buffer])

    assert progress_cancelled.is_set()
    assert sibling_cancelled.is_set()
    assert buffer.closed is True
    assert buffer.ensure_flushed_calls == 0


@pytest.mark.processor
@as_sync
async def test_download_lifecycle_success_closes_buffers_as_flushed():
    buffer = FakeBuffer()

    async def complete_block():
        await asyncio.sleep(0)

    await _run_download_lifecycle([complete_block()], [buffer])

    assert buffer.closed is True
    assert buffer.ensure_flushed_calls == 1


@pytest.mark.processor
@as_sync
async def test_download_lifecycle_unflushed_success_is_an_error_and_still_closes_buffer():
    buffer = FakeBuffer(unflushed=True)

    async def complete_block():
        await asyncio.sleep(0)

    with pytest.raises(RuntimeError, match="buffer 尚未清空"):
        await _run_download_lifecycle([complete_block()], [buffer])

    assert buffer.closed is True
    assert buffer.ensure_flushed_calls == 1


@pytest.mark.processor
@as_sync
async def test_download_lifecycle_cancellation_cancels_children_and_closes_buffers():
    block_started = asyncio.Event()
    block_cancelled = asyncio.Event()
    buffer = FakeBuffer()

    async def block():
        block_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            block_cancelled.set()

    lifecycle_task = asyncio.create_task(_run_download_lifecycle([block()], [buffer]))
    await block_started.wait()
    lifecycle_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await lifecycle_task

    assert block_cancelled.is_set()
    assert buffer.closed is True
    assert buffer.ensure_flushed_calls == 0
