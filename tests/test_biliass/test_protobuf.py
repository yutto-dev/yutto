from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from biliass import convert_to_ass

from ..conftest import DEFAULT_HEADERS, TEST_DIR

if TYPE_CHECKING:
    from pathlib import Path


def gen_protobuf(base_dir: Path):
    filename = "test.pb"
    filepath = base_dir / filename
    cid = "18678311"
    resp = httpx.get(
        f"http://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index={1}",
        headers=DEFAULT_HEADERS,
    )
    with filepath.open("wb") as f:
        f.write(resp.content)


@pytest.mark.biliass
def test_protobuf():
    gen_protobuf(TEST_DIR)
    with TEST_DIR.joinpath("test.pb").open("rb") as f:
        convert_to_ass(f.read(), 1920, 1080, input_format="protobuf")
