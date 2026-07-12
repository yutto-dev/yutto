from __future__ import annotations

from yutto.core.events import ApplicationEvent, DownloadBatchStarted, DownloadRequestQueued
from yutto.utils.console.logger import Badge, Logger


class CliApplicationEventRenderer:
    def emit(self, event: ApplicationEvent) -> None:
        match event:
            case DownloadBatchStarted(total=total):
                Logger.info(f"列表里共检测到 {total} 项")
            case DownloadRequestQueued(url=url, index=index, total=total):
                Logger.custom(f"列表项 {url}", Badge(f"[{index}/{total}]", fore="black", back="cyan"))
