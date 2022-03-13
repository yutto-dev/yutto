import os
import shutil

import pytest

TEST_DIR = "./__test_files__"


def pytest_sessionstart(session: pytest.Session):
    if not os.path.exists(TEST_DIR):
        os.mkdir(TEST_DIR)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
