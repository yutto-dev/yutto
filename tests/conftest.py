from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

TEST_DIR = Path("./__test_files__")
BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def pytest_sessionstart(session: pytest.Session):
    TEST_DIR.mkdir(exist_ok=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
