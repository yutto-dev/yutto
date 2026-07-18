from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactKind(StrEnum):
    MEDIA = "media"
    SUBTITLE = "subtitle"
    DANMAKU = "danmaku"
    METADATA = "metadata"
    COVER = "cover"


class ItemState(StrEnum):
    DONE = "done"
    SKIPPED = "skipped"


class ItemSkipReason(StrEnum):
    ALREADY_EXISTS = "already_exists"
    NO_MEDIA_STREAM = "no_media_stream"


class Artifact(_ResultModel):
    kind: ArtifactKind
    path: Path


class ItemResult(_ResultModel):
    state: ItemState
    output_path: Path
    skip_reason: ItemSkipReason | None = None
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_skip_reason(self) -> Self:
        if self.state is ItemState.DONE and self.skip_reason is not None:
            raise ValueError("done item must not have a skip reason")
        if self.state is ItemState.SKIPPED and self.skip_reason is None:
            raise ValueError("skipped item must have a skip reason")
        return self

    @property
    def has_downloaded_media(self) -> bool:
        return self.state is ItemState.DONE and any(artifact.kind is ArtifactKind.MEDIA for artifact in self.artifacts)


class DownloadResult(_ResultModel):
    items: tuple[ItemResult, ...] = Field(default_factory=tuple)


class ResolvedItem(_ResultModel):
    """A stable, listing-time snapshot of one episode; contains no expiring data."""

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


class ResolveFailure(_ResultModel):
    """一次预期内的解析失败（视频不存在 / 无访问权限 / 请求重试耗尽等）。

    ``type`` / ``message`` / ``code`` 与任务级错误（TaskError）同构，
    ``code`` 来自 yutto 的稳定错误码表。
    """

    type: str
    message: str
    code: int | str


class ResolveResult(_ResultModel):
    items: tuple[ResolvedItem, ...] = Field(default_factory=tuple)
    failures: tuple[ResolveFailure, ...] = Field(default_factory=tuple)
