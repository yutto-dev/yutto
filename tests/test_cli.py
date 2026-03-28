from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import pytest

from yutto.cli.cli import (
    add_auth_logout_arguments,
    add_auth_status_arguments,
    add_download_arguments,
    add_login_arguments,
    cli,
    handle_default_subcommand,
)
from yutto.cli.settings import YuttoSettings

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
