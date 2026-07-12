from __future__ import annotations

from pathlib import Path

import pytest

from yutto.path_templates import create_unique_path_resolver


@pytest.mark.processor
def test_unique_path():
    unique_path = create_unique_path_resolver()
    assert unique_path("a") == "a"
    assert unique_path("a") == "a (1)"
    assert unique_path("a") == "a (2)"

    # 首次调用原样返回，重名后的结果使用平台原生分隔符，按 Path 比较
    assert unique_path("/xxx/yyy/zzz.ext") == "/xxx/yyy/zzz.ext"
    assert Path(unique_path("/xxx/yyy/zzz.ext")) == Path("/xxx/yyy/zzz (1).ext")
    assert Path(unique_path("/xxx/yyy/zzz.ext")) == Path("/xxx/yyy/zzz (2).ext")
