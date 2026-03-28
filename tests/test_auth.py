from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from yutto.auth import format_auth_inline, load_auth, parse_auth_inline, remove_auth, resolve_auth, save_auth


def test_parse_auth_inline_handles_case_and_spaces():
    assert parse_auth_inline("  SESSDATA = foo ; BILI_JCT = bar  ") == {"SESSDATA": "foo", "bili_jct": "bar"}


def test_parse_auth_inline_requires_sessdata():
    assert parse_auth_inline("foo=bar; bili_jct=baz") is None


def test_format_auth_inline_omits_empty_bili_jct():
    assert format_auth_inline("foo") == "SESSDATA=foo"


def test_resolve_auth_prefers_inline_auth(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"
    save_auth(auth_file, "default", "from-file", "csrf")

    args = Namespace(
        auth="SESSDATA=from-inline; bili_jct=inline-csrf",
        auth_file=auth_file,
        auth_profile="default",
    )

    assert resolve_auth(args) == {"SESSDATA": "from-inline", "bili_jct": "inline-csrf"}


def test_resolve_auth_rejects_invalid_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"
    auth_file.write_text("[profiles.default]\nsessdata = 123\n", encoding="utf-8")

    args = Namespace(
        auth="",
        auth_file=auth_file,
        auth_profile="default",
    )

    with pytest.raises(ValueError, match="认证信息文件格式无效"):
        resolve_auth(args)


def test_save_and_load_auth_round_trip(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    save_auth(auth_file, "default", "sessdata-value", "csrf-value")

    assert load_auth(auth_file, "default") == {"SESSDATA": "sessdata-value", "bili_jct": "csrf-value"}


def test_save_auth_clears_stale_bili_jct(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    save_auth(auth_file, "default", "old-sessdata", "old-csrf")
    save_auth(auth_file, "default", "new-sessdata", None)

    assert load_auth(auth_file, "default") == {"SESSDATA": "new-sessdata", "bili_jct": None}
    assert "bili_jct" not in auth_file.read_text(encoding="utf-8")


def test_load_auth_returns_none_for_invalid_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"
    auth_file.write_text("[profiles.default]\nsessdata = 123\n", encoding="utf-8")

    assert load_auth(auth_file, "default") is None


def test_load_auth_rejects_invalid_profile(tmp_path: Path):
    with pytest.raises(ValueError, match="auth profile 名称不合法"):
        load_auth(tmp_path / "auth.toml", "bad profile")


def test_remove_auth_removes_target_profile_only(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    save_auth(auth_file, "default", "sessdata-default", "csrf-default")
    save_auth(auth_file, "work", "sessdata-work", "csrf-work")

    assert remove_auth(auth_file, "default")
    assert load_auth(auth_file, "default") is None
    assert load_auth(auth_file, "work") == {"SESSDATA": "sessdata-work", "bili_jct": "csrf-work"}


def test_remove_auth_deletes_empty_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    save_auth(auth_file, "default", "sessdata-value", "csrf-value")

    assert remove_auth(auth_file, "default")
    assert not auth_file.exists()


def test_remove_auth_returns_false_when_profile_missing(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"

    assert not remove_auth(auth_file, "default")


def test_remove_auth_rejects_invalid_existing_auth_file(tmp_path: Path):
    auth_file = tmp_path / "auth.toml"
    auth_file.write_text("[profiles.default]\nsessdata = 123\n", encoding="utf-8")

    with pytest.raises(ValueError, match="认证信息文件格式无效"):
        remove_auth(auth_file, "default")
