from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from yutto.core.events import DownloadProgress
from yutto.core.operation import emit_download_event

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Protocol

    from yutto.utils.file_buffer import AsyncFileBuffer

    class NativeTransferSnapshot(Protocol):
        @property
        def origin_bytes(self) -> int: ...

        @property
        def received_bytes(self) -> int: ...

        @property
        def committed_bytes(self) -> int: ...

        @property
        def window_saturated(self) -> bool: ...

    class NativeTransferHandle(Protocol):
        def done(self) -> bool: ...

        def snapshot(self) -> NativeTransferSnapshot: ...


SMOOTHING_WINDOW_SIZE = 10


async def show_progress(file_buffers: list[AsyncFileBuffer], total_size: int):
    t: float = time.time()
    size: int = sum([file_buffer.written_size for file_buffer in file_buffers])
    time_with_size_window = deque([(t, size)], maxlen=SMOOTHING_WINDOW_SIZE)
    while True:
        size_in_buffer: int = sum(
            [sum([len(chunk.data) for chunk in file_buffer.buffer]) for file_buffer in file_buffers]
        )
        size_written: int = sum([file_buffer.written_size for file_buffer in file_buffers])

        t_now = time.time()
        size_now = size_written + size_in_buffer
        time_with_size_window.append((t_now, size_now))
        speed = (size_now - time_with_size_window[0][1]) / (t_now - time_with_size_window[0][0] + 10**-6)
        emit_download_event(
            DownloadProgress(
                current=size_now,
                total=total_size,
                speed_per_second=speed,
                buffered_bytes=size_in_buffer,
            )
        )

        t, size = t_now, size_now
        await asyncio.sleep(0.25)
        if total_size == size:
            break


async def show_native_progress(handles: Sequence[NativeTransferHandle], total_size: int) -> None:
    t = time.time()
    transferred = sum(
        max(0, snapshot.received_bytes - snapshot.origin_bytes)
        for snapshot in (handle.snapshot() for handle in handles)
    )
    time_with_size_window = deque([(t, transferred)], maxlen=SMOOTHING_WINDOW_SIZE)
    while True:
        snapshots = [handle.snapshot() for handle in handles]
        size_now = min(total_size, sum(snapshot.received_bytes for snapshot in snapshots))
        buffered_bytes = min(
            size_now,
            sum(max(0, snapshot.received_bytes - snapshot.committed_bytes) for snapshot in snapshots),
        )
        transferred_now = sum(max(0, snapshot.received_bytes - snapshot.origin_bytes) for snapshot in snapshots)
        t_now = time.time()
        time_with_size_window.append((t_now, transferred_now))
        speed = (transferred_now - time_with_size_window[0][1]) / (t_now - time_with_size_window[0][0] + 10**-6)
        emit_download_event(
            DownloadProgress(
                current=size_now,
                total=total_size,
                speed_per_second=speed,
                buffered_bytes=buffered_bytes,
                is_congested=any(snapshot.window_saturated for snapshot in snapshots),
            )
        )
        if all(handle.done() for handle in handles):
            break
        await asyncio.sleep(0.25)
