import asyncio
import math
import time
from typing import Union

from yutto.utils.console.colorful import colored_string
from yutto.utils.console.formatter import size_format
from yutto.utils.console.logger import Logger
from yutto.utils.file_buffer import AsyncFileBuffer


class ProgressBar:
    def __init__(self, symbols: Union[str, list[str]] = "░▏▎▍▌▋▊▉█", width: int = 50):
        super().__init__()
        self.width = width
        self.symbols = symbols
        assert len(symbols) >= 2, "symbols 至少为 2 个"
        self.num_symbol = len(symbols)

    def render(self, data: float) -> str:
        if data == 1:
            return self.symbols[-1] * self.width
        length: float = self.width * data
        length_int: int = int(length)
        length_float: float = length - length_int

        return (
            length_int * self.symbols[-1]
            + self.symbols[math.floor(length_float * (self.num_symbol - 1))]
            + (self.width - length_int - 1) * self.symbols[0]
        )

    def end(self) -> str:
        return " " * (self.width + 40) + "\r"


async def show_progress(file_buffers: list[AsyncFileBuffer], total_size: int):
    file_buffers = list(filter(lambda x: x is not None, file_buffers))
    t = time.time()
    size = sum([file_buffer.written_size for file_buffer in file_buffers])
    progress_bar = ProgressBar(" ▏▎▍▌▋▊▉█")
    while True:
        size_in_buffer: int = sum(
            [sum([len(chunk.data) for chunk in file_buffer.buffer]) for file_buffer in file_buffers]
        )
        num_blocks_in_buffer: int = sum([len(file_buffer.buffer) for file_buffer in file_buffers])
        size_written: int = sum([file_buffer.written_size for file_buffer in file_buffers])

        t_now = time.time()
        size_now = size_written + size_in_buffer
        speed = (size_now - size) / (t_now - t + 10 ** -6)

        # 默认颜色为青色
        # 当速度过快导致 buffer 中的块数过多时（>1000 块），使用红色进行警告
        # 在速度高于 8MiB/s 时，使用绿色示意高速下载中
        color = "red" if num_blocks_in_buffer > 1000 else ("green" if speed >= 8 * 1024 * 1024 else "cyan")
        bar = colored_string(progress_bar.render(size_now / total_size), fore=color, back="white")
        # fmt: off
        Logger.print(
            "{} {:>10}/{:>10} {:>10}/s  ".format(
                bar,
                size_format(size_now),
                size_format(total_size),
                size_format(speed),
            ),
            end="\r",
        )

        t, size = t_now, size_now
        await asyncio.sleep(0.5)
        if total_size == size:
            Logger.print(progress_bar.end(), end="")
            break
