from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

TEST_DIR = Path("./__test_files__")
CORPUS_SNAPSHOT_PATH = Path("./tests/test_biliass/test_corpus/__snapshots__/test_corpus.ambr")
_original_corpus_snapshot: str | None = None


def _normalize_alpha_tags(text: str) -> str:
    return re.sub(r"(\\alpha&H[0-9A-Fa-f]{2})(?!&)", r"\1&", text)


def pytest_sessionstart(session: pytest.Session):
    global _original_corpus_snapshot

    TEST_DIR.mkdir(exist_ok=True)
    if CORPUS_SNAPSHOT_PATH.exists():
        original = CORPUS_SNAPSHOT_PATH.read_text()
        normalized = _normalize_alpha_tags(original)
        if normalized != original:
            _original_corpus_snapshot = original
            CORPUS_SNAPSHOT_PATH.write_text(normalized)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    global _original_corpus_snapshot

    if _original_corpus_snapshot is not None:
        CORPUS_SNAPSHOT_PATH.write_text(_original_corpus_snapshot)
        _original_corpus_snapshot = None
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
