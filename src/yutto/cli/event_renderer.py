from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self

from yutto.core.events import (
    DownloadBatchStarted,
    DownloadEvent,
    DownloadItemSkipped,
    DownloadProgress,
    DownloadRequestQueued,
    DownloadStageChanged,
)
from yutto.core.operation import ReportColor, ReportLevel
from yutto.core.result import ItemSkipReason
from yutto.utils.console.attributes import get_terminal_size
from yutto.utils.console.colorful import RGBColor, colored_string
from yutto.utils.console.formatter import get_char_width, get_string_width, size_format
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    from yutto.utils.console.colorful import Color, Style

PROGRESS_BAR_MIN_WIDTH = 10
PROGRESS_LABEL_MAX_WIDTH = 20
PROGRESS_LABEL_MIN_WIDTH = 10
PROGRESS_SIZE_MIN_WIDTH = 10
PROGRESS_SPEED_MIN_WIDTH = 12


def _render_bar(
    committed: int,
    buffered: int,
    total: int,
    committed_color: Color,
    buffered_color: Color,
    width: int,
) -> str:
    committed = min(max(committed, 0), total)
    buffered = min(max(buffered, 0), total - committed)
    received = committed + buffered

    half_width = width * 2
    committed_units = min(half_width, (half_width * committed + total - 1) // total)
    received_units = min(half_width, (half_width * received + total - 1) // total)

    remaining_color = RGBColor(64, 64, 64)
    runs: list[tuple[str, Color]] = []
    for cell in range(width):
        cell_start = cell * 2
        received_in_cell = min(2, max(0, received_units - cell_start))
        if received_in_cell == 0:
            glyph, color = "━", remaining_color
        else:
            glyph = "━" if received_in_cell == 2 else "╸"
            committed_in_cell = min(received_in_cell, max(0, committed_units - cell_start))
            color = committed_color if committed_in_cell > 0 else buffered_color

        if runs and runs[-1][1] == color:
            runs[-1] = (runs[-1][0] + glyph, color)
        else:
            runs.append((glyph, color))

    return "".join(colored_string(glyphs, fore=color) for glyphs, color in runs)


class CliApplicationEventRenderer:
    def __init__(self, *, progress_enabled: bool = True):
        self.progress_enabled = progress_enabled
        self._progress_items: set[str] = set()
        self._spinner_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Self:
        if self.progress_enabled:
            self._spinner_task = asyncio.create_task(self._run_spinner())
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._spinner_task is not None:
            self._spinner_task.cancel()
            await asyncio.gather(self._spinner_task, return_exceptions=True)
        Logger.status.reset()

    async def _run_spinner(self) -> None:
        while True:
            if not self._progress_items:
                Logger.status.next_tick()
            await asyncio.sleep(1)

    def report(
        self,
        message: str,
        level: ReportLevel,
        badge: str | None,
        color: ReportColor | None,
    ) -> None:
        if color is not None:
            report_colors: dict[ReportColor, Color] = {
                ReportColor.BLUE: "blue",
                ReportColor.GREEN: "green",
                ReportColor.MAGENTA: "magenta",
            }
            message = colored_string(message, fore=report_colors[color])
        if badge is not None:
            Logger.custom(message, Badge(badge, fore="black", back="cyan"))
            return
        match level:
            case ReportLevel.DEBUG:
                Logger.debug(message)
            case ReportLevel.ERROR:
                Logger.error(message)
            case ReportLevel.INFO:
                Logger.info(message)
            case ReportLevel.PLAIN:
                Logger.print(message)
            case ReportLevel.WARNING:
                Logger.warning(message)

    def emit(self, event: DownloadEvent) -> None:
        match event:
            case DownloadBatchStarted(total=total):
                Logger.info(f"列表里共检测到 {total} 项")
            case DownloadRequestQueued(url=url, index=index, total=total):
                Logger.custom(f"列表项 {url}", Badge(f"[{index}/{total}]", fore="black", back="cyan"))
            case DownloadStageChanged(item=item):
                self._finish_progress(item)
            case DownloadProgress() as progress:
                if self.progress_enabled:
                    self._progress_items.add(_progress_key(progress.item))
                    self._render_progress(progress)
            case DownloadItemSkipped(item=item, reason=ItemSkipReason.ALREADY_EXISTS):
                self._finish_progress(item)
                Logger.info(f"文件 {item} 已存在")
            case _:
                pass

    def _render_progress(self, progress: DownloadProgress) -> None:
        is_fast = progress.speed_per_second >= 8 * 1024 * 1024
        committed_color: Color = "green" if is_fast else "cyan"
        buffered_color: Color = "red" if progress.is_congested else "yellow"
        buffered_bytes = min(max(progress.buffered_bytes, 0), progress.current)
        committed_bytes = progress.current - buffered_bytes
        speed_color: Color = "green" if is_fast else "cyan"
        speed_style: list[Style] | None = ["bold"] if is_fast else None
        speed_suffix = "/⚡" if is_fast else "/s"
        current_text = f"{size_format(progress.current):>{PROGRESS_SIZE_MIN_WIDTH}}"
        total_text = f"{size_format(progress.total):>{PROGRESS_SIZE_MIN_WIDTH}}"
        speed_text = f"{size_format(progress.speed_per_second) + speed_suffix:>{PROGRESS_SPEED_MIN_WIDTH}}"
        stats_text = f"{current_text}/{total_text} {speed_text}  "
        rendered_stats = (
            f"{current_text}/{total_text} {colored_string(speed_text, fore=speed_color, style=speed_style)}  "
        )
        terminal_width = get_terminal_size()[0]
        available_width = max(0, terminal_width - get_string_width(stats_text))
        if progress.item is None:
            label_prefix = ""
            bar_width = min(max(0, available_width - 1), 50)
        else:
            label_width = min(PROGRESS_LABEL_MAX_WIDTH, max(0, available_width - 1))
            label_prefix = (
                f"{_fit_label(progress.item, label_width)} " if label_width >= PROGRESS_LABEL_MIN_WIDTH else ""
            )
            bar_width = min(max(0, available_width - PROGRESS_LABEL_MAX_WIDTH - 2), 50)
        bar = (
            _render_bar(
                committed_bytes,
                buffered_bytes,
                progress.total,
                committed_color,
                buffered_color,
                bar_width,
            )
            if bar_width >= PROGRESS_BAR_MIN_WIDTH and progress.total > 0
            else ""
        )
        rendered = f"{label_prefix}{bar + ' ' if bar else ''}{rendered_stats}"
        if progress.item is None:
            Logger.status.set(rendered)
        else:
            Logger.status.set_line(_progress_key(progress.item), rendered)

    def _finish_progress(self, item: str | None) -> None:
        if item is None:
            return
        key = _progress_key(item)
        if key not in self._progress_items:
            return
        self._progress_items.remove(key)
        if self.progress_enabled:
            Logger.status.remove_line(key)
            if not self._progress_items:
                Logger.status.next_tick()


def _progress_key(item: str | None) -> str:
    return item or "__download__"


def _truncate_label(item: str | None, max_width: int) -> str:
    if item is None or max_width < 1:
        return ""
    if get_string_width(item) <= max_width:
        return item

    suffix = "…"
    available = max_width - get_string_width(suffix)
    current = 0
    characters: list[str] = []
    for character in item:
        width = get_char_width(character)
        if current + width > available:
            break
        characters.append(character)
        current += width
    return "".join(characters) + suffix


def _fit_label(item: str, width: int) -> str:
    label = _truncate_label(item, width)
    return label + " " * max(0, width - get_string_width(label))
