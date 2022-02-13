import argparse
import asyncio
from typing import Any, Coroutine, Optional

import aiohttp

from yutto._typing import EpisodeData
from yutto.utils.console.logger import Logger


class Extractor:
    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        return (matched, url)

    def match(self, url: str) -> bool:
        raise NotImplementedError

    async def __call__(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> list[EpisodeData]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> list[EpisodeData]:
        episode_data = await self.extract(session, args)
        if episode_data is not None:
            return [episode_data]
        return []

    async def extract(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> Optional[EpisodeData]:
        """单话的只需要解析出来一话的数据即可，如果无法获取返回 None 即可，之后会自动过滤掉"""
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(self, session: aiohttp.ClientSession, args: argparse.Namespace) -> list[EpisodeData]:
        download_list: list[tuple[int, EpisodeData]] = []
        coroutine_list = await self.extract(session, args)
        num_videos = len(coroutine_list)
        # 先解析各种资源链接
        for i, coro in enumerate(asyncio.as_completed(coroutine_list)):
            Logger.status.set(f"正在努力解析第 {i+1}/{num_videos} 个视频")
            results = await coro
            if results is not None:
                download_list.append(results)

        # 由于 asyncio.as_completed 的顺序是按照完成顺序的，所以需要重新排序下
        download_list.sort(key=lambda x: x[0])

        return [item for _, item in download_list]

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Coroutine[Any, Any, Optional[tuple[int, EpisodeData]]]]:
        """为了并行化，批量下载需要返回协程任务列表，协程返回内容是一个元组，第一个位置是协程序号
        以便协程全部完成后恢复原顺序"""
        raise NotImplementedError
