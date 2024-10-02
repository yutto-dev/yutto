from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from biliass import convert_to_ass

from ..conftest import DEFAULT_HEADERS, TEST_DIR

if TYPE_CHECKING:
    from pathlib import Path


def gen_xml_v1(base_dir: Path):
    filename = "test_v1.xml"
    filepath = base_dir / filename
    cid = "18678311"
    resp = httpx.get(
        f"http://comment.bilibili.com/{cid}.xml",
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    )
    resp.encoding = "utf-8"
    with filepath.open("w", encoding="utf-8") as f:
        f.write(resp.text)


@pytest.mark.biliass
def test_xml_v1_text():
    gen_xml_v1(TEST_DIR)
    with TEST_DIR.joinpath("test_v1.xml").open("r") as f:
        convert_to_ass(f.read(), 1920, 1080)


@pytest.mark.biliass
def test_xml_v1_bytes():
    gen_xml_v1(TEST_DIR)
    with TEST_DIR.joinpath("test_v1.xml").open("rb") as f:
        convert_to_ass(f.read(), 1920, 1080)
