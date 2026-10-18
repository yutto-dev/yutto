from __future__ import annotations

import pytest

from yutto.utils.subtitle import Subtitle


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00,000"),
        (2.3, "00:00:02,300"),
        (4.35, "00:00:04,350"),
        (59.9996, "00:01:00,000"),
        (3661.5, "01:01:01,500"),
    ],
)
def test_subtitle_time_format_does_not_lose_milliseconds_to_float_error(seconds: float, expected: str):
    assert Subtitle.time_format(seconds) == expected
