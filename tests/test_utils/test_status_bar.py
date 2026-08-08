from __future__ import annotations

import pytest

import yutto.utils.console.status_bar as status_bar_module
from yutto.utils.console.status_bar import StatusBar


@pytest.fixture(autouse=True)
def reset_status_bar():
    StatusBar._enabled = False
    StatusBar._lines.clear()
    StatusBar._rendered_line_count = 0
    yield
    StatusBar._enabled = False
    StatusBar._lines.clear()
    StatusBar._rendered_line_count = 0


def test_status_bar_redraws_multiple_named_lines(monkeypatch: pytest.MonkeyPatch):
    output: list[tuple[str, str]] = []
    monkeypatch.setattr(
        status_bar_module,
        "print",
        lambda text, *, end: output.append((text, end)),
        raising=False,
    )
    StatusBar.enable()

    StatusBar.set_line("first", "line one")
    StatusBar.set_line("second", "line two")
    StatusBar.redraw()

    assert StatusBar._lines == {"first": "line one", "second": "line two"}
    assert StatusBar._rendered_line_count == 2
    assert ("line one", "\n") in output
    assert ("line two", "\r") in output
    assert ("\x1b[1A", "") in output


def test_spinner_does_not_replace_active_progress_line(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(status_bar_module, "print", lambda *args, **kwargs: None, raising=False)
    StatusBar.enable()
    StatusBar.set_line("download", "progress")

    StatusBar.next_tick()

    assert StatusBar._lines == {"download": "progress"}
