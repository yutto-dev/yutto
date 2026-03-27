from __future__ import annotations

from unittest.mock import patch

import pytest

from yutto.cli.cli import cli, handle_default_subcommand


@pytest.mark.processor
def test_handle_default_subcommand_keeps_download_compatibility():
    assert handle_default_subcommand(["BV1CrfKYLEeP"]) == ["download", "BV1CrfKYLEeP"]


@pytest.mark.processor
def test_removed_mcp_subcommand_surfaces_invalid_choice(capsys: pytest.CaptureFixture[str]):
    with patch("yutto.cli.cli.search_for_settings_file", return_value=None):
        parser = cli()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(handle_default_subcommand(["mcp"]))

    err = capsys.readouterr().err
    assert excinfo.value.code == 2
    assert "invalid choice" in err
    assert "mcp" in err
