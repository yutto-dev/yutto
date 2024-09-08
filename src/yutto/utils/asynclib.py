from __future__ import annotations

import asyncio
import platform
import time
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from yutto.utils.console.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Coroutine, Generator

RetT = TypeVar("RetT")


def initial_async_policy():
    if platform.system() == "Windows":
        Logger.debug("Windows 平台，单独设置 EventLoopPolicy")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore


class CoroutineWrapper(Generic[RetT]):
    coro: Coroutine[Any, Any, RetT]

    def __init__(self, coro: Coroutine[Any, Any, RetT]):
        self.coro = coro

    def __await__(self) -> Generator[Any, None, RetT]:
        return (yield from self.coro.__await__())

    def __del__(self):
        self.coro.close()


async def sleep_with_status_bar_refresh(seconds: float):
    current_time = start_time = time.time()
    while current_time - start_time < seconds:
        Logger.status.next_tick()
        await asyncio.sleep(min(1, seconds - (current_time - start_time)))
        current_time = time.time()
