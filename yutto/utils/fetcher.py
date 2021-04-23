import asyncio
from typing import Any, Optional

from aiohttp import ClientSession

from yutto.utils.logger import logger


class MaxRetryError(Exception):
    pass


class Fetcher:
    @classmethod
    async def fetch_text(cls, session: ClientSession, url: str, max_retry: int = 2) -> str:
        retry = max_retry + 1
        while retry:
            try:
                async with session.get(url) as resp:
                    return await resp.text()
            except asyncio.TimeoutError as e:
                logger.warning("url: {url} 抓取超时".format(url=url))
            finally:
                retry -= 1
        raise MaxRetryError()

    @classmethod
    async def fetch_json(cls, session: ClientSession, url: str, max_retry: int = 2) -> dict[str, Any]:
        retry = max_retry + 1
        while retry:
            try:
                async with session.get(url) as resp:
                    return await resp.json()
            except asyncio.TimeoutError as e:
                logger.warning("url: {url} 抓取超时".format(url=url))
            finally:
                retry -= 1
        raise MaxRetryError()

    @classmethod
    async def get_size(cls, session: ClientSession, url: str) -> Optional[int]:
        headers = session.headers.copy()
        headers["Range"] = "bytes=0-1"
        async with session.get(url, headers=headers) as resp:
            if resp.headers.get("Content-Length"):
                return int(resp.headers["Content-Range"].split("/")[-1])
            else:
                return None
