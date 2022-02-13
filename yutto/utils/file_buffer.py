import heapq
import os
from dataclasses import dataclass, field
from types import TracebackType
from typing import Optional, Type

import aiofiles

from yutto.utils.console.logger import Logger
from yutto.utils.functools import aobject


@dataclass(order=True)
class BufferChunk:
    offset: int
    data: bytes = field(compare=False)


class AsyncFileBuffer(aobject):
    """异步文件缓冲区

    Args:
        file_path (str): 所需存储文件位置
        overwrite (bool): 是否直接覆盖原文件

    Examples:
        .. code-block:: python

            async def afunc():
                buffer = await AsyncFileBuffer("/path/to/file", True)
                for i, chunk in enumerate([b'0', b'1', b'2', b'3', b'4']):
                    await buffer.write(chunk, i)
                await buffer.close()

                # 或者使用 async with（注意后面要有 await，因为 AsyncFileBuffer 的初始化是异步的）

                async with await AsyncFileBuffer("/path/to/file", True) as buffer:
                    for i, chunk in enumerate([b'0', b'1', b'2', b'3', b'4']):
                        await buffer.write(chunk, i)
    """

    # pyright: reportIncompatibleMethodOverride=false
    async def __ainit__(self, file_path: str, overwrite: bool = False):
        self.file_path = file_path
        if overwrite and os.path.exists(file_path):
            os.remove(file_path)
        self.buffer = list[BufferChunk]()
        self.written_size = os.path.getsize(file_path) if not overwrite and os.path.exists(file_path) else 0
        self.file_obj: Optional[aiofiles.threadpool.binary.AsyncBufferedIOBase] = await aiofiles.open(file_path, "ab")

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

    async def close(self):
        if self.buffer:
            Logger.error("buffer 尚未清空")
        if self.file_obj is not None:
            await self.file_obj.close()
        else:
            Logger.error("未预期的结果：未曾创建文件对象")

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        # __exit__ should exist in pair with __enter__ but never executed
        ...

    async def __aenter__(self) -> "AsyncFileBuffer":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()
