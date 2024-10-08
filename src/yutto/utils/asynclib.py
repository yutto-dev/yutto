from __future__ import annotations

import asyncio
import inspect
import platform
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from typing_extensions import ParamSpec

from yutto.utils.console.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator, Iterable

RetT = TypeVar("RetT")
P = ParamSpec("P")


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


def async_cache(
    args_to_cache_key: Callable[[inspect.BoundArguments], str],
) -> Callable[[Callable[P, Coroutine[Any, Any, RetT]]], Callable[P, Coroutine[Any, Any, RetT]]]:
    CACHE: dict[str, RetT] = {}

    def decorator(fn: Callable[P, Coroutine[Any, Any, RetT]]) -> Callable[P, Coroutine[Any, Any, RetT]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> RetT:
            sig = inspect.signature(fn)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            cache_key = args_to_cache_key(bound_args)
            if cache_key in CACHE:
                Logger.debug(f"{fn.__name__} cache hit: {cache_key}")
                return CACHE[cache_key]
            Logger.debug(f"{fn.__name__} cache miss: {cache_key}, all cache keys: {list(CACHE.keys())}")
            return CACHE.setdefault(cache_key, await fn(*args, **kwargs))

        return wrapper

    return decorator


async def first_successful(coros: Iterable[Coroutine[Any, Any, RetT]]) -> list[RetT]:
    tasks = [asyncio.create_task(coro) for coro in coros]

    results: list[RetT] = []
    while not results:
        done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        results = [task.result() for task in done if task.exception() is None]
    for task in tasks:
        task.cancel()
    return results


async def first_successful_with_check(coros: Iterable[Coroutine[Any, Any, RetT]]) -> RetT:
    results = await first_successful(coros)
    if not results:
        raise Exception("All coroutines failed")
    if len(set(results)) != 1:
        raise Exception("Multiple coroutines returned different results")
    return results[0]
