from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Iterable

RetT = TypeVar("RetT")
P = ParamSpec("P")


class NoSuccessfulResultError(Exception):
    """No raced operation completed successfully."""

    def __init__(self, exceptions: Iterable[Exception]):
        self.exceptions = tuple(exceptions)
        super().__init__("no raced operation completed successfully")


def make_coroutine_factory(
    fn: Callable[P, Coroutine[Any, Any, RetT]],
) -> Callable[P, Callable[[], Coroutine[Any, Any, RetT]]]:
    """绑定 coroutine function 的参数，延迟到 factory 调用时才创建 coroutine。"""

    def bind(*args: P.args, **kwargs: P.kwargs) -> Callable[[], Coroutine[Any, Any, RetT]]:
        return partial(fn, *args, **kwargs)

    return bind


async def race_for_first_success(factories: Iterable[Callable[[], Awaitable[RetT]]]) -> RetT:
    """Return the first successful value after reaping every started operation."""

    factory_list = tuple(factories)
    winner: list[RetT] = []
    failures: list[Exception] = []
    remaining = len(factory_list)
    completed = asyncio.Event()

    async def run(factory: Callable[[], Awaitable[RetT]]) -> None:
        nonlocal remaining
        try:
            value = await factory()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            failures.append(error)
        else:
            if not winner:
                winner.append(value)
        finally:
            remaining -= 1
            if winner or not remaining:
                completed.set()

    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(run(factory)) for factory in factory_list]
        if tasks:
            await completed.wait()
        for task in tasks:
            task.cancel()

    if winner:
        return winner[0]
    raise NoSuccessfulResultError(failures)
