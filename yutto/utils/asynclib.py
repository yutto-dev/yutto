import asyncio
from typing import Any, Coroutine, Iterable

from yutto.utils.console.logger import Logger

CoroutineTask = Coroutine[Any, Any, Any]


def install_uvloop():
    try:
        import uvloop
    except ImportError:
        Logger.warning("未安装 uvloop，无法使用其加速协程")
    else:
        uvloop.install()
        Logger.info("成功使用 uvloop 加速协程")


def parallel(funcs: Iterable[CoroutineTask]):
    return [asyncio.create_task(func) for func in funcs]


def parallel_with_limit(funcs: Iterable[CoroutineTask], num_workers: int = 4):
    tasks = asyncio.Queue[CoroutineTask]()
    for func in funcs:
        tasks.put_nowait(func)

    async def worker():
        while True:
            if not tasks.empty():
                task = await tasks.get()
                await task
            else:
                break

    return [asyncio.create_task(worker()) for _ in range(num_workers)]
