from __future__ import annotations

import pytest

from yutto.utils.console.formatter import get_char_width, get_string_width


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("a", 1),
        ("中", 2),
        ("⚡", 2),
        ("\u0301", 0),
    ],
)
def test_get_char_width(char: str, expected: int):
    assert get_char_width(char) == expected


def test_get_string_width():
    assert get_string_width("/⚡") == 3
