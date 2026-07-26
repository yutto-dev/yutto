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
from yutto.utils.console.formatter import size_format
from yutto.utils.console.logger import Badge, Logger

if TYPE_CHECKING:
    from yutto.utils.console.colorful import Color, Style


def _render_bar(data: float, color: Color, width: int) -> str:
    length = width * min(max(data, 0), 1)
    whole = int(length)
    if whole == width:
        return "━" * width
    symbol = "╸━"[int((length - whole) * 2)]
    return colored_string("━" * whole + symbol, fore=color) + colored_string(
        "━" * (width - whole - 1),
        fore=RGBColor(64, 64, 64),
    )


class CliApplicationEventRenderer:
    def __init__(self, *, progress_enabled: bool = True):
        self.progress_enabled = progress_enabled
        self._progress_active = False
        self._spinner_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Self:
        if self.progress_enabled:
            self._spinner_task = asyncio.create_task(self._run_spinner())
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._spinner_task is not None:
            self._spinner_task.cancel()
            await asyncio.gather(self._spinner_task, return_exceptions=True)
        Logger.status.clear()

    async def _run_spinner(self) -> None:
        while True:
            if not self._progress_active:
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
            case DownloadStageChanged():
                self._progress_active = False
            case DownloadProgress() as progress:
                if progress.buffered_blocks > 2048:
                    Logger.debug(f"number blocks in buffer: {progress.buffered_blocks}")
                if self.progress_enabled:
                    self._progress_active = True
                    self._render_progress(progress)
            case DownloadItemSkipped(item=item, reason=ItemSkipReason.ALREADY_EXISTS):
                Logger.info(f"文件 {item} 已存在")
            case _:
                pass

    def _render_progress(self, progress: DownloadProgress) -> None:
        is_fast = progress.speed_per_second >= 8 * 1024 * 1024
        is_congested = progress.buffered_blocks > 2048
        bar_color: Color = "red" if is_congested else ("green" if is_fast else "cyan")
        bar_width = min(get_terminal_size()[0] - 40, 50)
        bar = (
            _render_bar(progress.current / progress.total, bar_color, bar_width)
            if bar_width >= 10 and progress.total > 0
            else ""
        )
        speed_color: Color = "green" if is_fast else "cyan"
        speed_style: list[Style] | None = ["bold"] if is_fast else None
        speed_suffix = "/⚡" if is_fast else "/s"
        Logger.status.set(
            "{}{:>10}/{:>10} {:>12}  ".format(
                bar + " " if bar else "",
                size_format(progress.current),
                size_format(progress.total),
                colored_string(
                    size_format(progress.speed_per_second) + speed_suffix,
                    fore=speed_color,
                    style=speed_style,
                ),
            )
        )
