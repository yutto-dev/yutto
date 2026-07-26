from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import pytest

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
from yutto.core.events import DownloadProgress
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


def test_download_validation_rejects_non_positive_num_workers(monkeypatch: pytest.MonkeyPatch):
    args = make_download_parser().parse_args(["https://example.com", "--num-workers", "0"])
    errors: list[str] = []
    monkeypatch.setattr(validator_module, "FFmpeg", object)
    monkeypatch.setattr(validator_module.Logger, "error", errors.append)

    with pytest.raises(SystemExit) as exc_info:
        validator_module.validate_basic_arguments(args)

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert errors == ["num_workers 参数值（0）不满足要求哦（应为不小于 1 的整数）"]


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
    monkeypatch.setattr(renderer_module, "get_terminal_size", lambda: (80, 24))
    monkeypatch.setattr(renderer_module.Logger.status, "set", rendered.append)
    progress = DownloadProgress(current=1024, total=2048, speed_per_second=1024)

    renderer_module.CliApplicationEventRenderer(progress_enabled=False).emit(progress)
    assert rendered == []

    renderer_module.CliApplicationEventRenderer().emit(progress)
    assert len(rendered) == 1
    assert "1.00 KiB" in rendered[0]
    assert "2.00 KiB" in rendered[0]
