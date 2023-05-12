from __future__ import annotations

import asyncio
import platform
from collections.abc import Coroutine, Generator
from typing import Any, Generic, TypeVar

from yutto.utils.console.logger import Logger

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
