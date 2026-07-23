from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yutto.core.request import DownloadRequest

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from yutto.cli.settings import YuttoSettings

MEBIBYTE = 1024 * 1024


def download_request_from_namespace(args: argparse.Namespace) -> DownloadRequest:
    """Translate a fully parsed CLI namespace into the frontend-independent request model."""

    video_download_codec, video_save_codec = _split_codec_pair(args.vcodec, "vcodec")
    audio_download_codec, audio_save_codec = _split_codec_pair(args.acodec, "acodec")

    request: dict[str, Any] = {
        "source": {
            "url": args.url,
        },
        "access": {
            "auth_profile": args.auth_profile,
            "login_strict": args.login_strict,
            "vip_strict": args.vip_strict,
        },
        "scope": {
            "batch": args.batch,
            "with_section": args.with_section,
        },
        "selection": {
            "episodes": args.episodes,
            "start_time": args.batch_filter_start_time,
            "end_time": args.batch_filter_end_time,
        },
        "resources": {
            "video": args.require_video,
            "audio": args.require_audio,
            "danmaku": args.require_danmaku,
            "subtitle": args.require_subtitle,
            "metadata": args.require_metadata,
            "cover": args.require_cover,
            "chapter_info": args.require_chapter_info,
            "save_cover": args.save_cover,
            "ai_translation_language": args.ai_translation_language,
        },
        "stream": {
            "video_quality": args.video_quality,
            "audio_quality": args.audio_quality,
            "video_download_codec": video_download_codec,
            "video_save_codec": video_save_codec,
            "video_download_codec_priority": args.download_vcodec_priority,
            "audio_download_codec": audio_download_codec,
            "audio_save_codec": audio_save_codec,
        },
        "output": {
            "directory": args.dir,
            "temporary_directory": args.tmp_dir,
            "format": args.output_format,
            "audio_only_format": args.output_format_audio_only,
            "overwrite": args.overwrite,
            "subpath_template": args.subpath_template,
            "metadata_format_premiered": args.metadata_format_premiered,
            "mp_title_preset": args.mp_title_preset,
            "mp_as_multiple_version": args.mp_as_multiple_version,
        },
        "network": {
            "proxy": args.proxy,
            "fetch_workers": args.fetch_workers,
            "download_workers": args.num_workers,
            "block_size_bytes": int(args.block_size * MEBIBYTE),
            "download_interval": args.download_interval,
            "banned_mirrors_pattern": args.banned_mirrors_pattern,
        },
        "danmaku": {
            "format": args.danmaku_format,
            "font_size": args.danmaku_font_size,
            "font": args.danmaku_font,
            "opacity": args.danmaku_opacity,
            "display_region_ratio": args.danmaku_display_region_ratio,
            "speed": args.danmaku_speed,
            "block_top": args.danmaku_block_top or args.danmaku_block_fixed,
            "block_bottom": args.danmaku_block_bottom or args.danmaku_block_fixed,
            "block_scroll": args.danmaku_block_scroll,
            "block_reverse": args.danmaku_block_reverse,
            "block_special": args.danmaku_block_special,
            "block_colorful": args.danmaku_block_colorful,
            "block_keyword_patterns": args.danmaku_block_keyword_patterns or [],
        },
    }
    return DownloadRequest.model_validate(request)


def download_request_from_mapping(payload: object, settings: YuttoSettings) -> DownloadRequest:
    """Apply trusted local settings as defaults for an RPC request payload."""
    return download_request_parser_from_settings(settings)(payload)


def download_request_parser_from_settings(settings: YuttoSettings) -> Callable[[object], DownloadRequest]:
    """Build and eagerly validate a parser for repeated server requests."""
    defaults = _download_request_defaults_from_settings(settings)

    def parse(payload: object) -> DownloadRequest:
        if not isinstance(payload, dict):
            return DownloadRequest.model_validate(payload)
        return DownloadRequest.model_validate(_deep_merge(defaults, cast("dict[str, Any]", payload)))

    parse({"source": {"url": "yutto-server-default-validation"}})
    return parse


def _download_request_defaults_from_settings(settings: YuttoSettings) -> dict[str, Any]:
    video_download_codec, video_save_codec = _split_codec_pair(settings.basic.vcodec, "vcodec")
    audio_download_codec, audio_save_codec = _split_codec_pair(settings.basic.acodec, "acodec")
    danmaku = settings.danmaku
    return {
        "access": {
            "auth_profile": settings.auth.auth_profile,
            "login_strict": settings.basic.login_strict,
            "vip_strict": settings.basic.vip_strict,
        },
        "scope": {"batch": False, "with_section": settings.batch.with_section},
        "selection": {
            "episodes": "1~-1",
            "start_time": settings.batch.batch_filter_start_time,
            "end_time": settings.batch.batch_filter_end_time,
        },
        "resources": {
            "video": settings.resource.require_video,
            "audio": settings.resource.require_audio,
            "danmaku": settings.resource.require_danmaku,
            "subtitle": settings.resource.require_subtitle,
            "metadata": settings.resource.require_metadata,
            "cover": settings.resource.require_cover,
            "chapter_info": settings.resource.require_chapter_info,
            "save_cover": settings.resource.save_cover,
            "ai_translation_language": settings.basic.ai_translation_language,
        },
        "stream": {
            "video_quality": settings.basic.video_quality,
            "audio_quality": settings.basic.audio_quality,
            "video_download_codec": video_download_codec,
            "video_save_codec": video_save_codec,
            "video_download_codec_priority": settings.basic.download_vcodec_priority,
            "audio_download_codec": audio_download_codec,
            "audio_save_codec": audio_save_codec,
        },
        "output": {
            # ServerPolicy treats settings.basic.dir/tmp_dir as roots. Requests
            # select relative subdirectories beneath those roots.
            "directory": Path(),
            "temporary_directory": None,
            "format": settings.basic.output_format,
            "audio_only_format": settings.basic.output_format_audio_only,
            "overwrite": settings.basic.overwrite,
            "subpath_template": settings.basic.subpath_template,
            "metadata_format_premiered": settings.basic.metadata_format_premiered,
            "mp_title_preset": settings.basic.mp_title_preset,
            "mp_as_multiple_version": settings.basic.mp_as_multiple_version,
        },
        "network": {
            "proxy": settings.basic.proxy,
            "fetch_workers": settings.basic.fetch_workers,
            "download_workers": settings.basic.num_workers,
            "block_size_bytes": int(settings.basic.block_size * MEBIBYTE),
            "download_interval": settings.basic.download_interval,
            "banned_mirrors_pattern": settings.basic.banned_mirrors_pattern,
        },
        "danmaku": {
            "format": settings.basic.danmaku_format,
            "font_size": danmaku.font_size,
            "font": danmaku.font,
            "opacity": danmaku.opacity,
            "display_region_ratio": danmaku.display_region_ratio,
            "speed": danmaku.speed,
            "block_top": danmaku.block_top or danmaku.block_fixed,
            "block_bottom": danmaku.block_bottom or danmaku.block_fixed,
            "block_scroll": danmaku.block_scroll,
            "block_reverse": danmaku.block_reverse,
            "block_special": danmaku.block_special,
            "block_colorful": danmaku.block_colorful,
            "block_keyword_patterns": danmaku.block_keyword_patterns,
        },
    }


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in overrides.items():
        default = merged.get(key)
        if isinstance(default, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(
                cast("dict[str, Any]", default),
                cast("dict[str, Any]", value),
            )
        else:
            merged[key] = value
    return merged


def _split_codec_pair(value: str, option: str) -> tuple[str, str]:
    codecs = value.split(":")
    if len(codecs) != 2:
        raise ValueError(f"{option} must contain exactly one ':' separator")
    return codecs[0], codecs[1]
