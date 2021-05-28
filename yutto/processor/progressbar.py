import asyncio
import math
import time
from typing import Union, Optional

from yutto.utils.console.colorful import colored_string, Color, RGBColor, Style
from yutto.utils.console.formatter import size_format
from yutto.utils.console.logger import Logger
from yutto.utils.file_buffer import AsyncFileBuffer


class ProgressBar:
    def __init__(self, symbols: Union[str, list[str]] = "▏▎▍▌▋▊▉█", remaining_symbol: str = " ", width: int = 50):
        super().__init__()
        self.width = width
        self.symbols = symbols
        self.remaining_symbol = remaining_symbol
        assert len(symbols) >= 2, "symbols 至少为 2 个"
        self.num_symbol = len(symbols)

    def render(
        self,
        data: float,
        bar_fore_color: Optional[Color] = None,
        bar_back_color: Optional[Color] = None,
        remaining_bar_fore_color: Optional[Color] = None,
        remaining_bar_back_color: Optional[Color] = None,
    ) -> str:
        if data == 1:
            return self.symbols[-1] * self.width
        length: float = self.width * data
        length_int: int = int(length)
        length_float: float = length - length_int

        return colored_string(
            length_int * self.symbols[-1] + self.symbols[math.floor(length_float * self.num_symbol)],
            fore=bar_fore_color,
            back=bar_back_color,
        ) + colored_string(
            (self.width - length_int - 1) * self.remaining_symbol,
            fore=remaining_bar_fore_color,
            back=remaining_bar_back_color,
        )


async def show_progress(file_buffers: list[AsyncFileBuffer], total_size: int):
    file_buffers = list(filter(lambda x: x is not None, file_buffers))
    t = time.time()
    size = sum([file_buffer.written_size for file_buffer in file_buffers])
    progress_bar = ProgressBar("╸━", "━")
    while True:
        size_in_buffer: int = sum(
            [sum([len(chunk.data) for chunk in file_buffer.buffer]) for file_buffer in file_buffers]
        )
        num_blocks_in_buffer: int = sum([len(file_buffer.buffer) for file_buffer in file_buffers])
        size_written: int = sum([file_buffer.written_size for file_buffer in file_buffers])

        t_now = time.time()
        size_now = size_written + size_in_buffer
        speed = (size_now - size) / (t_now - t + 10 ** -6)

        # 进度条默认颜色为青色
        # 当速度过快导致 buffer 中的块数过多时（>2048 块，每块 2**15Bytes，缓冲区共 64MiB），使用红色进行警告
        # 在速度高于 8MiB/s 时，使用绿色示意高速下载中
        speed_threshold = 8 * 1024 * 1024
        is_fast = speed >= speed_threshold
        bar_color = "red" if num_blocks_in_buffer > 2048 else ("green" if is_fast else "cyan")
        bar = progress_bar.render(
            size_now / total_size, bar_fore_color=bar_color, remaining_bar_fore_color=RGBColor(64, 64, 64)
        )
        # 速度文本同时也使用绿色与青色作为速度标志
        speed_text_color: Color = "green" if is_fast else "cyan"
        speed_text_style: Optional[list[Style]] = ["bold"] if is_fast else None
        speed_text_suffix: str = "/⚡" if is_fast else "/s"
        # fmt: off
        Logger.status.set(
            "{} {:>10}/{:>10} {:>12}  ".format(
                bar,
                size_format(size_now),
                size_format(total_size),
                colored_string(size_format(speed)+speed_text_suffix, fore=speed_text_color, style=speed_text_style),
            )
        )
        # fmt: on

        t, size = t_now, size_now
        await asyncio.sleep(0.25)
        if total_size == size:
            break
