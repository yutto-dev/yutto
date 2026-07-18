from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path  # noqa: TC003 - runtime type hints are part of the event contract
from typing import Literal, Protocol, TypeAlias

from yutto.core.result import ItemSkipReason  # noqa: TC001 - runtime type hints support schema introspection


class DownloadStage(StrEnum):
    RESOLVING = "resolving"
    PREPARING = "preparing"
    WRITING_RESOURCES = "writing_resources"
    DOWNLOADING = "downloading"
    POSTPROCESSING = "postprocessing"


@dataclass(frozen=True, slots=True)
class DownloadBatchStarted:
    total: int


@dataclass(frozen=True, slots=True)
class DownloadRequestQueued:
    url: str
    index: int
    total: int


@dataclass(frozen=True, slots=True)
class DownloadStageChanged:
    name: DownloadStage
    item: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    current: int
    total: int
    speed_per_second: float
    phase: DownloadStage = DownloadStage.DOWNLOADING
    unit: Literal["bytes"] = "bytes"


@dataclass(frozen=True, slots=True)
class DownloadItemSkipped:
    item: str
    reason: ItemSkipReason


@dataclass(frozen=True, slots=True)
class DownloadArtifactCreated:
    item: str
    path: Path


@dataclass(frozen=True, slots=True)
class DownloadItemListed:
    """One episode enumerated during a resolve run; carries only stable listing data."""

    avid: str
    cid: str
    url: str
    name: str
    title: str
    cover_url: str
    planned_path: Path
    display_group: str | None = None
    uploader: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()


DownloadEvent: TypeAlias = (
    DownloadBatchStarted
    | DownloadRequestQueued
    | DownloadStageChanged
    | DownloadProgress
    | DownloadItemSkipped
    | DownloadArtifactCreated
    | DownloadItemListed
)


class DownloadEventSink(Protocol):
    def emit(self, event: DownloadEvent) -> None: ...


class NullDownloadEventSink:
    def emit(self, event: DownloadEvent) -> None:
        pass
