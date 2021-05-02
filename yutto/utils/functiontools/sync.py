import asyncio
from typing import Coroutine, Any, Callable, TypeVar

from functools import wraps

T = TypeVar("T")


def sync(async_func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    @wraps(async_func)
    def sync_func(*args: Any, **kwargs: Any):
        return asyncio.run(async_func(*args, **kwargs))

    return sync_func


if __name__ == "__main__":

    @sync
    async def run(a: int) -> int:
        return a

    print(run(1))
