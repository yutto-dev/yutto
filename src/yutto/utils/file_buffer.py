from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

import aiofiles

from yutto.utils.console.logger import Logger

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Protocol, Self

    class AsyncWritableBinaryFile(Protocol):
        async def write(self, data: bytes) -> int: ...

        async def close(self) -> None: ...


@dataclass(order=True)
class BufferChunk:
    offset: int
    data: bytes = field(compare=False)


class AsyncFileBuffer:
    """异步文件缓冲区

    ### Args

    - file_path (str): 所需存储文件位置
    - overwrite (bool): 是否直接覆盖原文件

    ### Examples:

    ``` python
    async def afunc():
        buffer = await AsyncFileBuffer.open("/path/to/file", overwrite=True)
        for i, chunk in enumerate([b'0', b'1', b'2', b'3', b'4']):
            await buffer.write(chunk, i)
        buffer.ensure_flushed()
        await buffer.close()

        # 或者使用 async with

        async with await AsyncFileBuffer.open("/path/to/file", overwrite=True) as buffer:
            for i, chunk in enumerate([b'0', b'1', b'2', b'3', b'4']):
                await buffer.write(chunk, i)
    ```
    """

    def __init__(
        self,
        file_path: Path,
        file_obj: AsyncWritableBinaryFile,
        written_size: int,
    ) -> None:
        self.file_path = file_path
        self.file_obj: AsyncWritableBinaryFile | None = file_obj
        self.written_size = written_size
        self.buffer: list[BufferChunk] = []

    @classmethod
    async def open(cls, file_path: str | Path, *, overwrite: bool = False) -> Self:
        """Open a file-backed buffer without changing normal construction semantics."""
        resolved_path = Path(file_path)
        if overwrite:
            resolved_path.unlink(missing_ok=True)
        written_size = resolved_path.stat().st_size if resolved_path.exists() else 0
        file_obj = cast("AsyncWritableBinaryFile", await aiofiles.open(resolved_path, "ab"))
        return cls(resolved_path, file_obj, written_size)

    async def write(self, chunk: bytes, offset: int):
        buffer_chunk = BufferChunk(offset, chunk)
        # 使用堆结构，保证第一个元素始终最小
        heapq.heappush(self.buffer, buffer_chunk)
        while self.buffer and self.buffer[0].offset <= self.written_size:
            assert self.file_obj is not None
            ready_to_write_chunk = heapq.heappop(self.buffer)
            if ready_to_write_chunk.offset < self.written_size:
                Logger.error(f"交叠的块范围 {ready_to_write_chunk.offset} < {self.written_size}，舍弃！")
                continue
            await self.file_obj.write(ready_to_write_chunk.data)
            self.written_size += len(ready_to_write_chunk.data)

    def ensure_flushed(self) -> None:
        if self.buffer:
            raise RuntimeError(f"buffer 尚未清空，仍有 {len(self.buffer)} 个分块")

    async def close(self) -> None:
        if self.file_obj is not None:
            await self.file_obj.close()
        else:
            Logger.error("未预期的结果：未曾创建文件对象")

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # __exit__ should exist in pair with __enter__ but never executed
        ...

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                self.ensure_flushed()
        finally:
            await self.close()
