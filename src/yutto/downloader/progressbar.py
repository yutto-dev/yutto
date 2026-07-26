from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from yutto.core.events import DownloadProgress
from yutto.core.operation import emit_download_event

if TYPE_CHECKING:
    from yutto.utils.file_buffer import AsyncFileBuffer

SMOOTHING_WINDOW_SIZE = 10


async def show_progress(file_buffers: list[AsyncFileBuffer], total_size: int):
    t: float = time.time()
    size: int = sum([file_buffer.written_size for file_buffer in file_buffers])
    time_with_size_window = deque([(t, size)], maxlen=SMOOTHING_WINDOW_SIZE)
    while True:
        size_in_buffer: int = sum(
            [sum([len(chunk.data) for chunk in file_buffer.buffer]) for file_buffer in file_buffers]
        )
        num_blocks_in_buffer: int = sum([len(file_buffer.buffer) for file_buffer in file_buffers])
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
                buffered_blocks=num_blocks_in_buffer,
            )
        )

        t, size = t_now, size_now
        await asyncio.sleep(0.25)
        if total_size == size:
            break
