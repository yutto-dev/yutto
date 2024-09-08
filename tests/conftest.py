from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

TEST_DIR = Path("./__test_files__")


def pytest_sessionstart(session: pytest.Session):
    TEST_DIR.mkdir(exist_ok=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
