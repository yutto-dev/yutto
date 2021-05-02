import asyncio
from typing import Any, Coroutine, Iterable

from yutto.utils.console.logger import Logger

try:
    import uvloop
except ImportError:
    Logger.warning("no install uvloop package")
else:
    # uvloop.install()
    pass

CoroutineTask = Coroutine[Any, Any, Any]


class LimitParallelsPool:
    """用于限制并行数的协程任务池

    Usage:

    ``` python
    async def cofunc():
        await asyncio.sleep(1)

    pool = LimitParallelsPool(num_workers=4)
    pool.add_list([cofunc() for _ in range(10)])
    asyncio.run(pool.run())
    ```
    """

    def __init__(self, num_workers: int = 5):
        self.num_workers = num_workers
        self._tasks = asyncio.Queue[CoroutineTask]()

    def add(self, task: CoroutineTask):
        self._tasks.put_nowait(task)

    def add_list(self, task_list: Iterable[CoroutineTask]):
        for task in task_list:
            self.add(task)

    async def run(self):
        workers = [asyncio.create_task(self._work()) for _ in range(self.num_workers)]
        for worker in workers:
            await worker

    async def _work(self):
        while True:
            if not self._tasks.empty():
                task = await self._tasks.get()
                await task
            else:
                break


def run_with_n_workers(tasks: Iterable[CoroutineTask], num_workers: int = 4):
    """限制并行数的基础上执行任务

    Args:
        tasks (Iterable[CoroutineTask]): 所需执行任务集合，需要为迭代器
        num_workers (int, optional): 最大并行数. Defaults to 4.
    """
    pool = LimitParallelsPool(num_workers=4)
    pool.add_list(tasks)
    asyncio.run(pool.run())


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
