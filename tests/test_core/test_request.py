from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

import yutto.__main__ as main_module
from yutto.cli.cli import add_download_arguments, cli, handle_default_subcommand
from yutto.cli.request_adapter import (
    download_request_from_mapping,
    download_request_from_namespace,
    download_request_parser_from_settings,
)
from yutto.cli.settings import YuttoSettings
from yutto.core.request import DownloadRequest

pytestmark = pytest.mark.processor


def parse_download_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_download_arguments(parser, YuttoSettings())
    return parser.parse_args(arguments)


def test_default_namespace_maps_to_grouped_core_request():
    request = download_request_from_namespace(parse_download_args(["BV1xx411c7mD"]))

    assert request.source.url == "BV1xx411c7mD"
    assert request.access.auth_profile == "default"
    assert request.scope.batch is False
    assert request.selection.episodes == "1~-1"
    assert request.resources.video is True
    assert request.resources.metadata is False
    assert request.stream.video_download_codec == "avc"
    assert request.stream.video_save_codec == "copy"
    assert request.output.directory == Path()
    assert request.network.block_size_bytes == 512 * 1024
    assert request.network.download_backend == "python"
    assert request.danmaku.format == "ass"


def test_namespace_adapter_preserves_download_semantics(tmp_path: Path):
    request = download_request_from_namespace(
        parse_download_args(
            [
                "BV1xx411c7mD",
                "--auth",
                "SESSDATA=token; bili_jct=csrf",
                "--auth-file",
                str(tmp_path / "auth.toml"),
                "--auth-profile",
                "secondary",
                "--login-strict",
                "--vip-strict",
                "--batch",
                "--episodes",
                "2,4~6",
                "--with-section",
                "--batch-filter-start-time",
                "2026-01-01",
                "--batch-filter-end-time",
                "2026-02-01",
                "--video-only",
                "--no-danmaku",
                "--no-subtitle",
                "--with-metadata",
                "--no-cover",
                "--no-chapter-info",
                "--ai-translation-language",
                "en",
                "--video-quality",
                "80",
                "--audio-quality",
                "30232",
                "--vcodec",
                "hevc:h264",
                "--acodec",
                "flac:aac",
                "--download-vcodec-priority",
                "hevc,avc,av1",
                "--dir",
                str(tmp_path / "output"),
                "--tmp-dir",
                str(tmp_path / "temporary"),
                "--output-format",
                "mkv",
                "--output-format-audio-only",
                "flac",
                "--overwrite",
                "--subpath-template",
                "{title}/{name}",
                "--metadata-format-premiered",
                "%Y",
                "--proxy",
                "no",
                "--fetch-workers",
                "3",
                "--num-workers",
                "4",
                "--block-size",
                "1.25",
                "--download-interval",
                "5",
                "--banned-mirrors-pattern",
                "example\\.com",
                "--danmaku-format",
                "protobuf",
                "--danmaku-font-size",
                "36",
                "--danmaku-font",
                "Sans",
                "--danmaku-opacity",
                "0.5",
                "--danmaku-display-region-ratio",
                "0.75",
                "--danmaku-speed",
                "1.5",
                "--danmaku-block-fixed",
                "--danmaku-block-scroll",
                "--danmaku-block-reverse",
                "--danmaku-block-special",
                "--danmaku-block-colorful",
                "--danmaku-block-keyword-patterns",
                "spoiler,广告",
            ]
        )
    )

    assert request.source.model_dump() == {"url": "BV1xx411c7mD"}
    assert request.access.model_dump() == {
        "auth_profile": "secondary",
        "login_strict": True,
        "vip_strict": True,
    }
    assert request.scope.model_dump() == {"batch": True, "with_section": True}
    assert request.selection.model_dump() == {
        "episodes": "2,4~6",
        "start_time": "2026-01-01",
        "end_time": "2026-02-01",
    }
    assert request.resources.model_dump() == {
        "video": True,
        "audio": False,
        "danmaku": False,
        "subtitle": False,
        "metadata": True,
        "cover": False,
        "chapter_info": False,
        "save_cover": False,
        "ai_translation_language": "en",
    }
    assert request.stream.model_dump() == {
        "video_quality": 80,
        "audio_quality": 30232,
        "video_download_codec": "hevc",
        "video_save_codec": "h264",
        "video_download_codec_priority": ["hevc", "avc", "av1"],
        "audio_download_codec": "flac",
        "audio_save_codec": "aac",
    }
    assert request.output.model_dump() == {
        "directory": tmp_path / "output",
        "temporary_directory": tmp_path / "temporary",
        "format": "mkv",
        "audio_only_format": "flac",
        "overwrite": True,
        "subpath_template": "{title}/{name}",
        "metadata_format_premiered": "%Y",
    }
    assert request.network.model_dump() == {
        "download_backend": "python",
        "proxy": "no",
        "fetch_workers": 3,
        "download_workers": 4,
        "block_size_bytes": 1_310_720,
        "download_interval": 5,
        "banned_mirrors_pattern": r"example\.com",
    }
    assert request.danmaku.model_dump() == {
        "format": "protobuf",
        "font_size": 36,
        "font": "Sans",
        "opacity": 0.5,
        "display_region_ratio": 0.75,
        "speed": 1.5,
        "block_top": True,
        "block_bottom": True,
        "block_scroll": True,
        "block_reverse": True,
        "block_special": True,
        "block_colorful": True,
        "block_keyword_patterns": ["spoiler", "广告"],
    }


def test_namespace_can_select_the_experimental_rust_backend():
    request = download_request_from_namespace(parse_download_args(["BV1xx411c7mD", "--download-backend", "rust"]))

    assert request.network.download_backend == "rust"


def test_cli_and_secret_options_do_not_cross_core_boundary(tmp_path: Path):
    request = download_request_from_namespace(
        parse_download_args(
            [
                "BV1xx411c7mD",
                "--auth",
                "SESSDATA=secret; bili_jct=secret",
                "--auth-file",
                str(tmp_path / "auth.toml"),
                "--sessdata",
                "legacy-secret",
                "--no-color",
                "--no-progress",
                "--debug",
                "--no-inherit",
            ]
        )
    )

    payload: dict[str, Any] = request.model_dump()
    excluded = {
        "auth",
        "auth_file",
        "sessdata",
        "no_color",
        "no_progress",
        "debug",
        "no_inherit",
        "config",
        "aliases",
    }
    assert not excluded & _all_keys(payload)
    assert "secret" not in request.model_dump_json()


def test_adapter_rejects_unvalidated_codec_pair():
    args = parse_download_args(["BV1xx411c7mD"])
    args.vcodec = "avc"

    with pytest.raises(ValueError, match="vcodec must contain exactly one"):
        download_request_from_namespace(args)


def test_cover_only_request_keeps_existing_save_cover_semantics():
    request = download_request_from_namespace(
        parse_download_args(
            [
                "BV1xx",
                "--cover-only",
            ]
        )
    )

    assert request.resources.cover is True
    assert request.resources.save_cover is True
    assert not any(
        (
            request.resources.video,
            request.resources.audio,
            request.resources.danmaku,
            request.resources.subtitle,
            request.resources.metadata,
            request.resources.chapter_info,
        )
    )


def test_core_rejects_save_cover_when_cover_is_disabled():
    with pytest.raises(ValueError, match="save_cover requires cover"):
        DownloadRequest.model_validate(
            {
                "source": {"url": "BV1xx"},
                "resources": {"cover": False, "save_cover": True},
            }
        )


@pytest.mark.parametrize("priority", [[], ["hevc", "av1"]])
def test_core_rejects_video_codec_priority_without_selected_codec(priority: list[str]):
    with pytest.raises(ValueError, match="video_download_codec"):
        DownloadRequest.model_validate(
            {
                "source": {"url": "BV1xx"},
                "stream": {
                    "video_download_codec": "avc",
                    "video_download_codec_priority": priority,
                },
            }
        )


def test_rpc_mapping_inherits_local_settings_without_credentials():
    settings = YuttoSettings.model_validate(
        {
            "basic": {
                "video_quality": 80,
                "proxy": "no",
                "dir": "configured-downloads",
                "tmp_dir": "configured-temporary",
                "sessdata": "legacy-secret",
            },
            "resource": {"require_subtitle": False, "require_metadata": True},
            "auth": {
                "auth": "SESSDATA=inline-secret",
                "auth_profile": "work",
            },
            "danmaku": {"block_fixed": True},
        }
    )
    request = download_request_from_mapping(
        {
            "source": {"url": "BV1xx"},
            "stream": {"video_quality": 116},
        },
        settings,
    )

    assert request.access.auth_profile == "work"
    assert request.stream.video_quality == 116
    assert request.network.proxy == "no"
    assert request.resources.subtitle is False
    assert request.resources.metadata is True
    assert request.danmaku.block_top is True
    assert request.danmaku.block_bottom is True
    assert request.output.directory == Path()
    assert "inline-secret" not in request.model_dump_json()
    assert "legacy-secret" not in request.model_dump_json()


def test_task_list_preserves_per_item_network_and_auth_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    task_list = tmp_path / "downloads.txt"
    task_list.write_text(
        "\n".join(
            [
                "BV1first --proxy no --fetch-workers 2 --num-workers 3 --auth-profile first",
                "BV1second --no-inherit --proxy auto --fetch-workers 5 --num-workers 7 --auth-profile second",
            ]
        ),
        encoding="utf-8",
    )
    parser = cli()
    args = parser.parse_args(
        handle_default_subcommand(
            [
                str(task_list),
                "--proxy",
                "https://127.0.0.1:7890",
                "--fetch-workers",
                "11",
                "--num-workers",
                "13",
                "--auth-profile",
                "outer",
            ]
        )
    )
    monkeypatch.setattr(main_module, "validate_basic_arguments", lambda args: None)

    requests = [download_request_from_namespace(item) for item in main_module.flatten_args(args, parser)]

    assert [
        (
            request.source.url,
            request.network.proxy,
            request.network.fetch_workers,
            request.network.download_workers,
            request.access.auth_profile,
        )
        for request in requests
    ] == [
        ("BV1first", "no", 2, 3, "first"),
        ("BV1second", "auto", 5, 7, "second"),
    ]


def test_server_request_parser_validates_configured_defaults_eagerly():
    settings = YuttoSettings.model_validate({"basic": {"vcodec": "invalid-pair"}})

    with pytest.raises(ValueError, match="vcodec must contain exactly one"):
        download_request_parser_from_settings(settings)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys: set[str] = set()
        for key, item in value.items():
            if isinstance(key, str):
                keys.add(key)
            keys.update(_all_keys(item))
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys.update(_all_keys(item))
        return keys
    return set()
