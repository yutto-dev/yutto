from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable

RetT = TypeVar("RetT")
P = ParamSpec("P")


def make_coroutine_factory(
    fn: Callable[P, Coroutine[Any, Any, RetT]],
) -> Callable[P, Callable[[], Coroutine[Any, Any, RetT]]]:
    """绑定 coroutine function 的参数，延迟到 factory 调用时才创建 coroutine。"""

    def bind(*args: P.args, **kwargs: P.kwargs) -> Callable[[], Coroutine[Any, Any, RetT]]:
        return partial(fn, *args, **kwargs)

    return bind


async def first_successful(coros: Iterable[Coroutine[Any, Any, RetT]]) -> list[RetT]:
    tasks = [asyncio.create_task(coro) for coro in coros]

    results: list[RetT] = []
    try:
        while not results:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            results = [task.result() for task in done if task.exception() is None]
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        raise
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
