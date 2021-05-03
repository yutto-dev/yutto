import asyncio
import time

from yutto.utils.console.formatter import size_format
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.console.logger import Logger


async def show_progress(file_buffers: list[AsyncFileBuffer], total_size: int):
    file_buffers = list(filter(lambda x: x is not None, file_buffers))
    t = time.time()
    size = sum([file_buffer.written_size for file_buffer in file_buffers])
    while True:
        size_in_buffer: int = sum(
            [sum([len(chunk.data) for chunk in file_buffer.buffer]) for file_buffer in file_buffers]
        )
        size_written: int = sum([file_buffer.written_size for file_buffer in file_buffers])

        t_now = time.time()
        size_now = size_written + size_in_buffer
        speed = (size_now - size) / (t_now - t + 10 ** -6)

        Logger.print(
            "[File: {:>10} + Buffer: {:>10}({:>4} 块)]/{:>10} {:>10}/s".format(
                size_format(size_written),
                size_format(size_in_buffer),
                sum([len(file_buffer.buffer) for file_buffer in file_buffers]),
                size_format(total_size),
                size_format(speed),
            ),
            end="\r",
        )
        t, size = t_now, size_now
        await asyncio.sleep(0.5)
        if total_size == size:
            break
