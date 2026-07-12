from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import yutto.__main__ as main_module
import yutto.server.command as server_command_module
from yutto.cli.cli import cli, handle_default_subcommand
from yutto.exceptions import ErrorCode
from yutto.server.command import resolve_server_token

pytestmark = pytest.mark.processor


def test_serve_is_an_explicit_subcommand():
    assert handle_default_subcommand(["serve"]) == ["serve"]
    args = cli().parse_args(["serve", "--port", "12345", "--allow-origin", "https://ui.example"])
    assert args.command == "serve"
    assert args.port == 12345
    assert args.allow_origin == ["https://ui.example"]


def test_serve_io_error_is_rendered_without_traceback(monkeypatch: pytest.MonkeyPatch):
    parser = SimpleNamespace(parse_args=lambda args: SimpleNamespace(command="serve"))
    rendered_errors: list[str] = []

    def fail_server(args: object) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(main_module, "cli", lambda: parser)
    monkeypatch.setattr(main_module.sys, "argv", ["yutto", "serve"])
    monkeypatch.setattr(server_command_module, "run_server_command", fail_server)
    monkeypatch.setattr(main_module.Logger, "error", rendered_errors.append)

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == ErrorCode.WRONG_ARGUMENT_ERROR.value
    assert rendered_errors == ["address already in use"]


def test_environment_token_takes_precedence(tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("file-token\n", encoding="utf-8")

    resolved = resolve_server_token(token_file, environ={"YUTTO_SERVER_TOKEN": " environment-token "})

    assert resolved.value == "environment-token"
    assert resolved.generated is False
    assert resolved.persisted_to is None


def test_missing_token_file_is_created_with_a_generated_token(tmp_path):
    token_file = tmp_path / "private" / "server.token"

    resolved = resolve_server_token(token_file, environ={})

    assert resolved.generated is True
    assert resolved.persisted_to == token_file
    assert token_file.read_text(encoding="utf-8").strip() == resolved.value
    if os.name != "nt":
        assert token_file.stat().st_mode & 0o777 == 0o600


def test_empty_token_file_is_rejected(tmp_path):
    token_file = tmp_path / "empty.token"
    token_file.write_text("\n", encoding="utf-8")
    if os.name != "nt":
        token_file.chmod(0o600)

    with pytest.raises(ValueError, match="为空"):
        resolve_server_token(token_file, environ={})


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions only")
def test_existing_token_file_must_be_private_and_cannot_be_a_symlink(tmp_path):
    public_token = tmp_path / "public.token"
    public_token.write_text("secret\n", encoding="utf-8")
    public_token.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        resolve_server_token(public_token, environ={})

    private_token = tmp_path / "private.token"
    private_token.write_text("secret\n", encoding="utf-8")
    private_token.chmod(0o600)
    linked_token = tmp_path / "linked.token"
    linked_token.symlink_to(private_token)
    with pytest.raises(ValueError, match="安全读取"):
        resolve_server_token(linked_token, environ={})
