from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import pytest

from yutto.cli.cli import add_download_arguments, add_login_arguments
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
