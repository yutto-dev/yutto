from __future__ import annotations

import asyncio

import pytest

from yutto.downloader.downloader import _run_download_lifecycle
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


class FakeBuffer:
    def __init__(self) -> None:
        self.closed = False
        self.warn_unflushed: bool | None = None

    async def close(self, *, warn_unflushed: bool = True) -> None:
        self.closed = True
        self.warn_unflushed = warn_unflushed


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
    assert buffer.warn_unflushed is False


@pytest.mark.processor
@as_sync
async def test_download_lifecycle_success_closes_buffers_as_flushed():
    buffer = FakeBuffer()

    async def complete_block():
        await asyncio.sleep(0)

    await _run_download_lifecycle([complete_block()], [buffer])

    assert buffer.closed is True
    assert buffer.warn_unflushed is True


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
    assert buffer.warn_unflushed is False
