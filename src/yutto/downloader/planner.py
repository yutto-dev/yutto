from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from yutto.downloader.selector import select_audio, select_video
from yutto.utils.time import TIME_FULL_FMT

if TYPE_CHECKING:
    from pathlib import Path

    from yutto.core.request import DownloadRequest
    from yutto.media.codec import AudioCodec, VideoCodec
    from yutto.media.quality import AudioQuality, VideoQuality
    from yutto.types import AudioUrlMeta, EpisodeData, VideoUrlMeta
    from yutto.utils.danmaku import DanmakuSaveType


@dataclass(frozen=True, slots=True)
class DownloadPaths:
    output_dir: Path
    temporary_dir: Path
    output: Path
    video: Path
    audio: Path
    cover: Path
    saved_cover: Path
    chapter_info: Path


@dataclass(frozen=True, slots=True)
class VideoStream:
    index: int
    url: str = field(repr=False)
    mirrors: tuple[str, ...] = field(repr=False)
    codec: VideoCodec
    width: int
    height: int
    quality: VideoQuality


@dataclass(frozen=True, slots=True)
class AudioStream:
    index: int
    url: str = field(repr=False)
    mirrors: tuple[str, ...] = field(repr=False)
    codec: AudioCodec
    quality: AudioQuality


@dataclass(frozen=True, slots=True)
class DanmakuPlan:
    font_size: int | None
    font: str
    opacity: float
    display_region_ratio: float
    speed: float
    block_top: bool
    block_bottom: bool
    block_scroll: bool
    block_reverse: bool
    block_special: bool
    block_colorful: bool
    block_keyword_patterns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetadataPlan:
    premiered: str
    dateadded: str


@dataclass(frozen=True, slots=True)
class DownloadResources:
    """Frozen write policy; large extractor payloads remain in EpisodeData."""

    subtitle_languages: tuple[str, ...]
    has_danmaku: bool
    danmaku_save_type: DanmakuSaveType | None
    has_metadata: bool
    has_cover: bool
    has_chapter_info: bool
    save_cover: bool
    danmaku_width: int
    danmaku_height: int
    metadata: MetadataPlan
    danmaku: DanmakuPlan


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    """A side-effect-free description of one download."""

    item: str
    paths: DownloadPaths
    video: VideoStream | None
    audio: AudioStream | None
    media_requested: bool
    video_save_codec: str
    audio_save_codec: str
    attach_hvc1_tag: bool
    requires_audio_transcode_notice: bool
    overwrite: bool
    download_backend: str
    block_size: int
    banned_mirrors_pattern: str | None
    resources: DownloadResources

    @property
    def has_media(self) -> bool:
        return self.video is not None or self.audio is not None


class DownloadPlanner:
    """Turn extractor data plus a request into a pure download plan."""

    def plan(self, episode_data: EpisodeData, request: DownloadRequest) -> DownloadPlan:
        video_candidate = select_video(
            episode_data["videos"],
            request.stream.video_quality,
            request.stream.video_download_codec,
            request.stream.video_download_codec_priority,
        )
        audio_candidate = select_audio(
            episode_data["audios"],
            request.stream.audio_quality,
            request.stream.audio_download_codec,
        )
        video_meta = video_candidate if request.resources.video else None
        audio_meta = audio_candidate if request.resources.audio else None
        suffix = resolve_output_suffix(video_meta, audio_meta, request)
        paths = resolve_paths(
            request.output.directory,
            request.output.temporary_directory or request.output.directory,
            episode_data["info"]["path"],
            suffix,
        )

        video_save_codec = request.stream.video_save_codec
        attach_hvc1_tag = should_attach_hvc1_tag(video_meta, video_save_codec)
        if video_meta is not None and video_meta["codec"] == video_save_codec:
            video_save_codec = "copy"

        requested_audio_save_codec = request.stream.audio_save_codec
        audio_save_codec = (
            resolve_audio_save_codec(audio_meta["codec"], requested_audio_save_codec, suffix)
            if audio_meta is not None
            else requested_audio_save_codec
        )

        selected_video_index = (
            episode_data["videos"].index(video_candidate)
            if video_candidate is not None and request.resources.video
            else -1
        )
        selected_audio_index = (
            episode_data["audios"].index(audio_candidate)
            if audio_candidate is not None and request.resources.audio
            else -1
        )
        resources = DownloadResources(
            subtitle_languages=tuple(subtitle["lang"] for subtitle in episode_data["subtitles"]),
            has_danmaku=bool(episode_data["danmaku"]["data"]),
            danmaku_save_type=episode_data["danmaku"]["save_type"],
            has_metadata=episode_data["metadata"] is not None,
            has_cover=episode_data["cover_data"] is not None,
            has_chapter_info=bool(episode_data["chapter_info_data"]),
            save_cover=request.resources.save_cover,
            danmaku_width=video_candidate["width"] if video_candidate is not None else 1920,
            danmaku_height=video_candidate["height"] if video_candidate is not None else 1080,
            metadata=MetadataPlan(
                premiered=request.output.metadata_format_premiered,
                dateadded=TIME_FULL_FMT,
            ),
            danmaku=DanmakuPlan(
                font_size=request.danmaku.font_size,
                font=request.danmaku.font,
                opacity=request.danmaku.opacity,
                display_region_ratio=request.danmaku.display_region_ratio,
                speed=request.danmaku.speed,
                block_top=request.danmaku.block_top,
                block_bottom=request.danmaku.block_bottom,
                block_scroll=request.danmaku.block_scroll,
                block_reverse=request.danmaku.block_reverse,
                block_special=request.danmaku.block_special,
                block_colorful=request.danmaku.block_colorful,
                block_keyword_patterns=tuple(request.danmaku.block_keyword_patterns),
            ),
        )
        return DownloadPlan(
            item=episode_data["info"]["path"].name,
            paths=paths,
            video=freeze_video_stream(video_meta, selected_video_index),
            audio=freeze_audio_stream(audio_meta, selected_audio_index),
            media_requested=request.resources.video or request.resources.audio,
            video_save_codec=video_save_codec,
            audio_save_codec=audio_save_codec,
            attach_hvc1_tag=attach_hvc1_tag,
            requires_audio_transcode_notice=(
                audio_meta is not None and audio_save_codec not in {requested_audio_save_codec, "copy"}
            ),
            overwrite=request.output.overwrite,
            download_backend=request.network.download_backend,
            block_size=request.network.block_size_bytes,
            banned_mirrors_pattern=request.network.banned_mirrors_pattern,
            resources=resources,
        )


def resolve_paths(
    base_output_dir: Path,
    base_temporary_dir: Path,
    path: Path,
    output_suffix: str,
) -> DownloadPaths:
    output_full_path = base_output_dir / path
    output_dir, filename = output_full_path.parent, output_full_path.name
    temporary_full_path = base_temporary_dir / path
    temporary_dir, temporary_filename = temporary_full_path.parent, temporary_full_path.name
    assert filename == temporary_filename, (
        f"Filename should be the same in output and tmp dir, but got {filename} and {temporary_filename}"
    )
    return DownloadPaths(
        output_dir=output_dir,
        temporary_dir=temporary_dir,
        output=output_dir / f"{filename}{output_suffix}",
        video=temporary_dir / f"{filename}_video.m4s",
        audio=temporary_dir / f"{filename}_audio.m4s",
        cover=temporary_dir / f"{filename}_cover.jpg",
        saved_cover=output_dir / f"{filename}-poster.jpg",
        chapter_info=temporary_dir / f"{filename}_chapter_info.ini",
    )


def resolve_output_suffix(
    video: VideoUrlMeta | None,
    audio: AudioUrlMeta | None,
    request: DownloadRequest,
) -> str:
    if video is None:
        if request.output.audio_only_format != "infer":
            return f".{request.output.audio_only_format}"
        if audio is not None and audio["codec"] == "flac" and request.stream.audio_save_codec in {"copy", "flac"}:
            return ".flac"
        if audio is not None and audio["codec"] == "eac3" and request.stream.audio_save_codec in {"copy", "eac3"}:
            return ".mkv"
        return ".m4a"

    if request.output.format != "infer":
        return f".{request.output.format}"
    if audio is not None and audio["codec"] == "flac":
        return ".mkv"
    return ".mp4"


def freeze_video_stream(video: VideoUrlMeta | None, index: int) -> VideoStream | None:
    if video is None:
        return None
    return VideoStream(
        index=index,
        url=video["url"],
        mirrors=tuple(video["mirrors"]),
        codec=video["codec"],
        width=video["width"],
        height=video["height"],
        quality=video["quality"],
    )


def freeze_audio_stream(audio: AudioUrlMeta | None, index: int) -> AudioStream | None:
    if audio is None:
        return None
    return AudioStream(
        index=index,
        url=audio["url"],
        mirrors=tuple(audio["mirrors"]),
        codec=audio["codec"],
        quality=audio["quality"],
    )


def should_attach_hvc1_tag(video: VideoUrlMeta | None, video_save_codec: str) -> bool:
    """Whether the output needs the Apple-compatible hvc1 tag."""
    return (
        video is not None
        and video["quality"] != 126
        and (video_save_codec == "hevc" or (video_save_codec == "copy" and video["codec"] == "hevc"))
    )


SINGLE_CODEC_AUDIO_CONTAINERS: dict[str, tuple[frozenset[str], str]] = {
    ".mp3": (frozenset({"mp3"}), "mp3"),
    ".flac": (frozenset({"flac"}), "flac"),
    ".aac": (frozenset({"mp4a", "aac"}), "aac"),
}


def resolve_audio_save_codec(audio_codec: str, audio_save_codec: str, container_suffix: str) -> str:
    """Resolve the actual audio codec after the output container is known."""
    if audio_codec == audio_save_codec:
        return "copy"
    if audio_save_codec == "copy" and (rule := SINGLE_CODEC_AUDIO_CONTAINERS.get(container_suffix)) is not None:
        compatible_codecs, transcode_codec = rule
        if audio_codec not in compatible_codecs:
            return transcode_codec
    return audio_save_codec
