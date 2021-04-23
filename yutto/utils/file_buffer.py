import bisect
import os
from typing import NamedTuple, Optional

import aiofiles
from aiofiles import os as aioos

from yutto.utils.logger import logger


class BufferChunk(NamedTuple):
    chunk: Optional[bytes]
    offset: int


class AsyncFileBuffer:
    def __init__(self):
        self.file_obj: Optional[aiofiles.threadpool.binary.AsyncBufferedIOBase] = None
        self.buffer = list[BufferChunk]()
        self.written_size = 0

    @classmethod
    async def create(cls, file_path: str, overwrite: bool = False):
        self = cls()
        if overwrite and os.path.exists(file_path):
            await aioos.remove(file_path)
        self.written_size = os.path.getsize(file_path) if os.path.exists(file_path) and not overwrite else 0
        self.file_obj = await aiofiles.open(file_path, "r+b")
        await self._seek(self.written_size)
        return self

    async def write(self, chunk: bytes, offset: int):
        buffer_chunk = BufferChunk(chunk, offset)
        index = bisect.bisect([offset for (_, offset) in self.buffer], buffer_chunk.offset)
        self.buffer.insert(index, buffer_chunk)

        while self.buffer and self.buffer[0].offset <= self.written_size:
            assert self.file_obj is not None
            ready_to_write_chunk = self.buffer.pop(0)
            assert ready_to_write_chunk.chunk is not None
            if ready_to_write_chunk.offset < self.written_size:
                await self._seek(ready_to_write_chunk.offset)
                logger.warning("[WARNING] 文件指针回溯！")
            await self.file_obj.write(ready_to_write_chunk.chunk)
            self.written_size += len(ready_to_write_chunk.chunk)

    async def close(self):
        assert self.file_obj is not None, "无法关闭未创建的文件对象"
        await self.file_obj.close()

    async def _seek(self, offset: int):
        assert self.file_obj is not None
        await self.file_obj.seek(offset)
        self.written_size = offset
