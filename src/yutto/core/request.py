from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yutto.media.codec import AudioCodec, VideoCodec
from yutto.media.quality import AudioQuality, VideoQuality
from yutto.utils.time import TIME_DATE_FMT


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRequestOptions(_RequestModel):
    """The source to resolve."""

    url: str


class AccessRequestOptions(_RequestModel):
    """Authentication profile and access checks, without credential material."""

    auth_profile: str = "default"
    login_strict: bool = False
    vip_strict: bool = False


class ScopeRequestOptions(_RequestModel):
    """Whether resolution targets one episode or an expanded collection."""

    batch: bool = False
    with_section: bool = False


class SelectionRequestOptions(_RequestModel):
    """Filters applied while selecting episodes from an expanded scope."""

    episodes: str = "1~-1"
    start_time: str | None = None
    end_time: str | None = None


class ResourceRequestOptions(_RequestModel):
    """Resources that should be present in the resulting download."""

    video: bool = True
    audio: bool = True
    danmaku: bool = True
    subtitle: bool = True
    metadata: bool = False
    cover: bool = True
    chapter_info: bool = True
    save_cover: bool = False
    ai_translation_language: str | None = None

    @model_validator(mode="after")
    def enable_save_cover_for_cover_only(self) -> Self:
        if self.save_cover and not self.cover:
            raise ValueError("save_cover requires cover")
        if self.cover and not any(
            (
                self.video,
                self.audio,
                self.danmaku,
                self.subtitle,
                self.metadata,
                self.chapter_info,
            )
        ):
            self.save_cover = True
        return self


class StreamRequestOptions(_RequestModel):
    """Media stream quality and codec preferences."""

    video_quality: VideoQuality = 127
    audio_quality: AudioQuality = 30251
    video_download_codec: VideoCodec = "avc"
    video_save_codec: str = "copy"
    video_download_codec_priority: list[VideoCodec] | None = None
    audio_download_codec: AudioCodec = "mp4a"
    audio_save_codec: str = "copy"

    @model_validator(mode="after")
    def validate_video_codec_priority(self) -> Self:
        priority = self.video_download_codec_priority
        if priority is not None and not priority:
            raise ValueError("video_download_codec_priority must not be empty")
        if priority is not None and self.video_download_codec not in priority:
            raise ValueError("video_download_codec must be included in video_download_codec_priority")
        return self


class OutputRequestOptions(_RequestModel):
    """Output paths, containers, and naming preferences."""

    directory: Path = Field(default_factory=Path)
    temporary_directory: Path | None = None
    format: Literal["infer", "mp4", "mkv", "mov"] = "infer"
    audio_only_format: Literal["infer", "m4a", "aac", "mp3", "flac", "mp4", "mkv", "mov"] = "infer"
    overwrite: bool = False
    subpath_template: str = "{auto}"
    metadata_format_premiered: str = TIME_DATE_FMT
    enforce_directory_boundary: bool = Field(default=False, exclude=True)


class NetworkRequestOptions(_RequestModel):
    """Network access and transfer concurrency preferences."""

    proxy: str = "auto"
    fetch_workers: int = 8
    download_workers: int = 8
    block_size_bytes: int = 512 * 1024
    download_interval: int = 0
    banned_mirrors_pattern: str | None = None


class DanmakuRequestOptions(_RequestModel):
    """Danmaku serialization, rendering, and filtering preferences."""

    format: Literal["xml", "ass", "protobuf"] = "ass"
    font_size: int | None = None
    font: str = "SimHei"
    opacity: float = 0.8
    display_region_ratio: float = 1.0
    speed: float = 1.0
    block_top: bool = False
    block_bottom: bool = False
    block_scroll: bool = False
    block_reverse: bool = False
    block_special: bool = False
    block_colorful: bool = False
    block_keyword_patterns: list[str] = Field(default_factory=list)


class DownloadRequest(_RequestModel):
    """A fully resolved, frontend-independent request to yutto's core."""

    source: SourceRequestOptions
    access: AccessRequestOptions = Field(default_factory=AccessRequestOptions)
    scope: ScopeRequestOptions = Field(default_factory=ScopeRequestOptions)
    selection: SelectionRequestOptions = Field(default_factory=SelectionRequestOptions)
    resources: ResourceRequestOptions = Field(default_factory=ResourceRequestOptions)
    stream: StreamRequestOptions = Field(default_factory=StreamRequestOptions)
    output: OutputRequestOptions = Field(default_factory=OutputRequestOptions)
    network: NetworkRequestOptions = Field(default_factory=NetworkRequestOptions)
    danmaku: DanmakuRequestOptions = Field(default_factory=DanmakuRequestOptions)
