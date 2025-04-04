from __future__ import annotations

import asyncio
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


R = TypeVar("R")
P = ParamSpec("P")


def as_sync(async_func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    """将异步函数变成同步函数，避免在调用时需要显式使用 asyncio.run

    ### Examples

    ``` python

    # 不使用 sync
    async def itoa(a: int) -> str:
        return str(a)

    s: str = asyncio.run(itoa(1))

    # 使用 sync
    @as_sync
    async def itoa(a: int) -> str:
        return str(a)
    s: str = itoa(1)
    ```
    """

    @wraps(async_func)
    def sync_func(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(async_func(*args, **kwargs))

    return sync_func


if __name__ == "__main__":

    @as_sync
    async def run(a: int) -> int:
        return a

    print(run(1))
