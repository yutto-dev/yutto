import heapq
import os
from dataclasses import dataclass, field
from typing import Optional

import aiofiles

from yutto.utils.console.logger import Logger


@dataclass(order=True)
class BufferChunk:
    offset: int
    data: bytes = field(compare=False)


class AsyncFileBuffer:
    def __init__(self):
        self.file_path = ""
        self.file_obj: Optional[aiofiles.threadpool.binary.AsyncBufferedIOBase] = None
        self.buffer = list[BufferChunk]()
        self.written_size = 0

    @classmethod
    async def create(cls, file_path: str, overwrite: bool = False):
        self = cls()
        self.file_path = file_path
        if overwrite and os.path.exists(file_path):
            os.remove(file_path)
        self.written_size = os.path.getsize(file_path) if not overwrite and os.path.exists(file_path) else 0
        self.file_obj = await aiofiles.open(file_path, "ab")
        return self

    async def write(self, chunk: bytes, offset: int):
        buffer_chunk = BufferChunk(offset, chunk)
        # 使用堆结构，保证第一个元素始终最小
        heapq.heappush(self.buffer, buffer_chunk)
        while self.buffer and self.buffer[0].offset <= self.written_size:
            assert self.file_obj is not None
            ready_to_write_chunk = heapq.heappop(self.buffer)
            if ready_to_write_chunk.offset < self.written_size:
                Logger.error("交叠的块范围 {} < {}，舍弃！".format(ready_to_write_chunk.offset, self.written_size))
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
