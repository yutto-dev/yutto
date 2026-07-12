from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias


@dataclass(frozen=True, slots=True)
class DownloadBatchStarted:
    total: int


@dataclass(frozen=True, slots=True)
class DownloadRequestQueued:
    url: str
    index: int
    total: int


ApplicationEvent: TypeAlias = DownloadBatchStarted | DownloadRequestQueued


class ApplicationEventSink(Protocol):
    def emit(self, event: ApplicationEvent) -> None: ...


class NullApplicationEventSink:
    def emit(self, event: ApplicationEvent) -> None:
        pass
