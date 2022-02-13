import asyncio
from typing import Coroutine, Any, Callable, TypeVar

from functools import wraps

T = TypeVar("T")


def as_sync(async_func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """将异步函数变成同步函数，避免在调用时需要显式使用 asyncio.run

    Examples:
        .. code-block:: python

            # 不使用 sync
            async def itoa(a: int) -> str:
                return str(a)

            s: str = asyncio.run(itoa(1))

            # 使用 sync
            @as_sync
            async def itoa(a: int) -> str:
                return str(a)
            s: str = itoa(1)
    """

    @wraps(async_func)
    def sync_func(*args: Any, **kwargs: Any):
        return asyncio.run(async_func(*args, **kwargs))

    return sync_func


if __name__ == "__main__":

    @as_sync
    async def run(a: int) -> int:
        return a

    print(run(1))
