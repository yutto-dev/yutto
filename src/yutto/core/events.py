from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias

if TYPE_CHECKING:
    from pathlib import Path

    from yutto.core.result import ItemSkipReason, ResolvedItem
    from yutto.media.codec import AudioCodec, VideoCodec
    from yutto.media.quality import AudioQuality, VideoQuality


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
    # CLI-local buffer telemetry; intentionally excluded from the v1 task event payload.
    buffered_bytes: int = 0
    is_congested: bool = False
    item: str | None = None


@dataclass(frozen=True, slots=True)
class SelectedVideoStream:
    codec: VideoCodec
    quality: VideoQuality
    width: int
    height: int
    save_codec: str


@dataclass(frozen=True, slots=True)
class SelectedAudioStream:
    codec: AudioCodec
    quality: AudioQuality
    save_codec: str


@dataclass(frozen=True, slots=True)
class DownloadMediaSelected:
    item: str
    video: SelectedVideoStream | None
    audio: SelectedAudioStream | None


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
    """One episode enumerated during a resolve run."""

    item: ResolvedItem


DownloadEvent: TypeAlias = (
    DownloadBatchStarted
    | DownloadRequestQueued
    | DownloadStageChanged
    | DownloadProgress
    | DownloadMediaSelected
    | DownloadItemSkipped
    | DownloadArtifactCreated
    | DownloadItemListed
)


class DownloadEventSink(Protocol):
    def emit(self, event: DownloadEvent) -> None: ...


class NullDownloadEventSink:
    def emit(self, event: DownloadEvent) -> None:
        pass
