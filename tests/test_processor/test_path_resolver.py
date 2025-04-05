from __future__ import annotations

import pytest

from yutto.path_resolver import create_unique_path_resolver


@pytest.mark.processor
def test_unique_path():
    unique_path = create_unique_path_resolver()
    assert unique_path("a") == "a"
    assert unique_path("a") == "a (1)"
    assert unique_path("a") == "a (2)"

    assert unique_path("/xxx/yyy/zzz.ext") == "/xxx/yyy/zzz.ext"
    assert unique_path("/xxx/yyy/zzz.ext") == "/xxx/yyy/zzz (1).ext"
    assert unique_path("/xxx/yyy/zzz.ext") == "/xxx/yyy/zzz (2).ext"
