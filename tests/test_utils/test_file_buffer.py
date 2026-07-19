from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.processor


@as_sync
async def test_async_file_buffer_open_preserves_existing_data(tmp_path: Path):
    path = tmp_path / "buffer.bin"
    path.write_bytes(b"existing")

    async with await AsyncFileBuffer.open(path) as buffer:
        assert buffer.written_size == len(b"existing")
        await buffer.write(b"-appended", len(b"existing"))

    assert path.read_bytes() == b"existing-appended"


@as_sync
async def test_async_file_buffer_open_can_overwrite_existing_data(tmp_path: Path):
    path = tmp_path / "buffer.bin"
    path.write_bytes(b"existing")

    async with await AsyncFileBuffer.open(path, overwrite=True) as buffer:
        assert buffer.written_size == 0
        await buffer.write(b"replacement", 0)

    assert path.read_bytes() == b"replacement"
