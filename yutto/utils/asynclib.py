import asyncio
import platform
from typing import Any, Coroutine, TypeVar, Callable
from functools import wraps


from yutto.utils.console.logger import Logger

T = TypeVar("T")


def initial_async_policy():
    if platform.system() == "Windows":
        Logger.debug("Windows 平台，单独设置 EventLoopPolicy")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def install_uvloop():
    try:
        import uvloop
    except ImportError:
        Logger.warning("未安装 uvloop，无法使用其加速协程")
    else:
        uvloop.install()
        Logger.info("成功使用 uvloop 加速协程")


async def awaited_value(value: T) -> T:
    return value


def with_semaphore(
    func: Callable[..., Coroutine[Any, Any, T]], sem: asyncio.Semaphore
) -> Callable[..., Coroutine[Any, Any, T]]:
    @wraps(func)
    async def limited_func(*args: Any, **kwargs: Any) -> T:
        async with sem:
            return await func(*args, **kwargs)

    return limited_func
