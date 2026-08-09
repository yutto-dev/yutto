from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

import pytest

import yutto.__main__ as main_module
import yutto.cli.event_renderer as renderer_module
import yutto.validator as validator_module
from yutto.cli.cli import (
    add_auth_logout_arguments,
    add_auth_status_arguments,
    add_download_arguments,
    add_login_arguments,
    cli,
    handle_default_subcommand,
)
from yutto.cli.settings import YuttoSettings
from yutto.core.events import DownloadProgress, DownloadStage, DownloadStageChanged
from yutto.core.execution import RequestExecutionScopeFactory
from yutto.core.operation import (
    ReportColor,
    ReportLevel,
    bind_download_report_sink,
    emit_download_report,
)
from yutto.exceptions import ErrorCode

if TYPE_CHECKING:
    from pathlib import Path


def make_settings() -> YuttoSettings:
    return YuttoSettings.model_validate({})


def make_download_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_download_arguments(parser, make_settings())
    return parser


def make_login_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_login_arguments(parser, make_settings())
    return parser


def make_auth_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_auth_status_arguments(parser, make_settings())
    return parser


def make_auth_logout_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_auth_logout_arguments(parser, make_settings())
    return parser


def test_download_parser_accepts_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = make_download_parser().parse_args(["https://example.com", "--auth-file", str(auth_file)])

    assert args.auth_file == auth_file


def test_download_parser_rejects_auth_config(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    with pytest.raises(SystemExit) as exc_info:
        make_download_parser().parse_args(["https://example.com", "--auth-config", str(auth_file)])

    assert exc_info.value.code == 2


def test_download_parser_accepts_ffmpeg_path():
    parser = make_download_parser()

    assert parser.parse_args(["https://example.com"]).ffmpeg_path == "ffmpeg"
    assert (
        parser.parse_args(["https://example.com", "--ffmpeg-path", "/opt/ffmpeg/ffmpeg"]).ffmpeg_path
        == "/opt/ffmpeg/ffmpeg"
    )


def test_download_passes_ffmpeg_path_to_ffmpeg(monkeypatch: pytest.MonkeyPatch):
    recorded: dict[str, str] = {}

    class RecordingFFmpeg:
        def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
            recorded["path"] = ffmpeg_path
            raise RuntimeError("stop after recording")

    monkeypatch.setattr(validator_module, "FFmpeg", RecordingFFmpeg)
    args = make_download_parser().parse_args(["https://example.com", "--ffmpeg-path", "/opt/ffmpeg/ffmpeg"])
    with pytest.raises(RuntimeError, match="stop after recording"):
        validator_module.validate_basic_arguments(args)

    assert recorded["path"] == "/opt/ffmpeg/ffmpeg"


def test_download_validation_rejects_non_positive_num_workers(monkeypatch: pytest.MonkeyPatch):
    args = make_download_parser().parse_args(["https://example.com", "--num-workers", "0"])
    errors: list[str] = []
    monkeypatch.setattr(validator_module, "FFmpeg", lambda _path: object())
    monkeypatch.setattr(validator_module.Logger, "error", errors.append)

    with pytest.raises(SystemExit) as exc_info:
        validator_module.validate_basic_arguments(args)

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert errors == ["num_workers 参数值（0）不满足要求哦（应为不小于 1 的整数）"]


def test_download_jobs_default_to_one_and_reject_non_positive_values(monkeypatch: pytest.MonkeyPatch):
    parser = make_download_parser()
    assert parser.parse_args(["https://example.com"]).jobs == 1
    args = parser.parse_args(["https://example.com", "--jobs", "0"])
    errors: list[str] = []
    monkeypatch.setattr(validator_module, "FFmpeg", lambda _path: object())
    monkeypatch.setattr(validator_module.Logger, "error", errors.append)

    with pytest.raises(SystemExit) as exc_info:
        validator_module.validate_basic_arguments(args)

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert errors == ["jobs 参数值（0）不满足要求哦（应为不小于 1 的整数）"]


def test_login_parser_accepts_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = make_login_parser().parse_args(["--auth-file", str(auth_file)])

    assert args.auth_file == auth_file


def test_login_parser_rejects_auth_config(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    with pytest.raises(SystemExit) as exc_info:
        make_login_parser().parse_args(["--auth-config", str(auth_file)])

    assert exc_info.value.code == 2


def test_auth_status_parser_accepts_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = make_auth_status_parser().parse_args(["--auth-file", str(auth_file)])

    assert args.auth_file == auth_file


def test_auth_logout_parser_accepts_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = make_auth_logout_parser().parse_args(["--auth-file", str(auth_file)])

    assert args.auth_file == auth_file


def test_root_parser_accepts_auth_login(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = cli().parse_args(["auth", "login", "--auth-file", str(auth_file)])

    assert args.command == "auth"
    assert args.auth_command == "login"
    assert args.auth_file == auth_file


def test_root_parser_accepts_auth_status(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = cli().parse_args(["auth", "status", "--auth-file", str(auth_file)])

    assert args.command == "auth"
    assert args.auth_command == "status"
    assert args.auth_file == auth_file


def test_root_parser_accepts_auth_logout(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    args = cli().parse_args(["auth", "logout", "--auth-file", str(auth_file)])

    assert args.command == "auth"
    assert args.auth_command == "logout"
    assert args.auth_file == auth_file


def test_root_parser_rejects_removed_top_level_login():
    with pytest.raises(SystemExit) as exc_info:
        cli().parse_args(handle_default_subcommand(["login"]))

    assert exc_info.value.code == 2


def test_progress_renderer_respects_no_progress(monkeypatch: pytest.MonkeyPatch):
    rendered: list[str] = []
    debug_messages: list[str] = []
    monkeypatch.setattr(renderer_module, "get_terminal_size", lambda: (80, 24))
    monkeypatch.setattr(renderer_module.Logger.status, "set", rendered.append)
    monkeypatch.setattr(renderer_module.Logger, "debug", debug_messages.append)
    progress = DownloadProgress(
        current=1024,
        total=2048,
        speed_per_second=1024,
        buffered_bytes=512,
        is_congested=True,
    )

    renderer_module.CliApplicationEventRenderer(progress_enabled=False).emit(progress)
    assert rendered == []
    assert debug_messages == []

    renderer_module.CliApplicationEventRenderer().emit(progress)
    assert len(rendered) == 1
    assert "1.00 KiB" in rendered[0]
    assert "2.00 KiB" in rendered[0]
    assert debug_messages == []


def test_progress_bar_renders_committed_buffered_and_remaining_segments(monkeypatch: pytest.MonkeyPatch):
    rendered_segments: list[tuple[str, object]] = []
    monkeypatch.setattr(
        renderer_module,
        "colored_string",
        lambda text, *, fore, **_: rendered_segments.append((text, fore)) or text,
    )

    assert renderer_module._render_bar(4, 2, 8, "cyan", "yellow", 8) == "━" * 8
    assert rendered_segments == [
        ("━" * 4, "cyan"),
        ("━" * 2, "yellow"),
        ("━" * 2, renderer_module.RGBColor(64, 64, 64)),
    ]

    rendered_segments.clear()
    renderer_module._render_bar(500_000_000, 1, 1_000_000_000, "cyan", "yellow", 50)
    assert rendered_segments == [
        ("━" * 25, "cyan"),
        ("╸", "yellow"),
        ("━" * 24, renderer_module.RGBColor(64, 64, 64)),
    ]

    rendered_segments.clear()
    renderer_module._render_bar(500_000_001, 0, 1_000_000_000, "cyan", "yellow", 50)
    assert rendered_segments == [
        ("━" * 25 + "╸", "cyan"),
        ("━" * 24, renderer_module.RGBColor(64, 64, 64)),
    ]

    rendered_segments.clear()
    renderer_module._render_bar(500_000_001, 1, 1_000_000_000, "cyan", "yellow", 50)
    assert rendered_segments == [
        ("━" * 25 + "╸", "cyan"),
        ("━" * 24, renderer_module.RGBColor(64, 64, 64)),
    ]

    rendered_segments.clear()
    renderer_module._render_bar(9, 1, 16, "cyan", "yellow", 8)
    assert rendered_segments == [
        ("━" * 5, "cyan"),
        ("━" * 3, renderer_module.RGBColor(64, 64, 64)),
    ]

    rendered_segments.clear()
    renderer_module._render_bar(8, 2, 16, "cyan", "yellow", 8)
    assert rendered_segments == [
        ("━" * 4, "cyan"),
        ("━", "yellow"),
        ("━" * 3, renderer_module.RGBColor(64, 64, 64)),
    ]


def test_progress_renderer_turns_only_buffered_segment_red(monkeypatch: pytest.MonkeyPatch):
    rendered_bars: list[tuple[object, ...]] = []
    monkeypatch.setattr(renderer_module, "get_terminal_size", lambda: (80, 24))
    monkeypatch.setattr(
        renderer_module,
        "_render_bar",
        lambda *args: rendered_bars.append(args) or "bar",
    )
    monkeypatch.setattr(renderer_module.Logger.status, "set", lambda _message: None)

    renderer = renderer_module.CliApplicationEventRenderer()
    renderer.emit(
        DownloadProgress(
            current=1024,
            total=2048,
            speed_per_second=1024,
            buffered_bytes=512,
            is_congested=False,
        )
    )
    renderer.emit(
        DownloadProgress(
            current=1024,
            total=2048,
            speed_per_second=1024,
            buffered_bytes=512,
            is_congested=True,
        )
    )

    assert rendered_bars == [
        (512, 512, 2048, "cyan", "yellow", 40),
        (512, 512, 2048, "cyan", "red", 40),
    ]


def test_progress_renderer_tracks_multiple_items_and_removes_completed_rows(monkeypatch: pytest.MonkeyPatch):
    rendered: list[tuple[str, str]] = []
    removed: list[str] = []
    monkeypatch.setattr(renderer_module, "get_terminal_size", lambda: (100, 24))
    monkeypatch.setattr(renderer_module.Logger.status, "set_line", lambda key, text: rendered.append((key, text)))
    monkeypatch.setattr(renderer_module.Logger.status, "remove_line", removed.append)
    monkeypatch.setattr(renderer_module.Logger.status, "next_tick", lambda: None)

    renderer = renderer_module.CliApplicationEventRenderer()
    renderer.emit(DownloadProgress(current=1, total=2, speed_per_second=3, item="视频一"))
    renderer.emit(DownloadProgress(current=2, total=4, speed_per_second=5, item="视频二"))
    renderer.emit(DownloadStageChanged(name=DownloadStage.POSTPROCESSING, item="视频一"))

    assert [key for key, _ in rendered] == ["视频一", "视频二"]
    assert "视频一" in rendered[0][1]
    assert "视频二" in rendered[1][1]
    assert removed == ["视频一"]


def test_progress_labels_are_truncated_by_terminal_width():
    assert renderer_module._truncate_label("short", 10) == "short"
    assert renderer_module._truncate_label("一二三四五六", 7) == "一二三…"


def test_run_download_scopes_report_renderer_and_cleans_up_on_cancel(monkeypatch: pytest.MonkeyPatch):
    output: list[tuple[str, object]] = []

    async def cancel_download(_application: object, _requests: object) -> None:
        emit_download_report("warning", ReportLevel.WARNING)
        emit_download_report("badge", badge="TAG", color=ReportColor.GREEN)
        raise asyncio.CancelledError

    monkeypatch.setattr(main_module.YuttoApplication, "download_all", cancel_download)
    monkeypatch.setattr(renderer_module.Logger, "warning", lambda message: output.append(("warning", message)))
    monkeypatch.setattr(
        renderer_module.Logger,
        "custom",
        lambda message, badge: output.append(("badge", (message, badge.text))),
    )
    monkeypatch.setattr(renderer_module.Logger.status, "reset", lambda: output.append(("cleared", True)))
    monkeypatch.setattr(renderer_module, "colored_string", lambda message, *, fore, **_: f"{fore}:{message}")

    emit_download_report("unbound")
    with bind_download_report_sink(lambda message, *_: output.append(("outer", message))):
        with pytest.raises(asyncio.CancelledError):
            main_module.run_download(RequestExecutionScopeFactory(), [], renderer_module.CliApplicationEventRenderer())
        emit_download_report("outer")

    assert output == [
        ("warning", "warning"),
        ("badge", ("green:badge", "TAG")),
        ("cleared", True),
        ("outer", "outer"),
    ]
