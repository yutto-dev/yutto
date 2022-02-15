import argparse
from typing import Any, Coroutine, Optional, TypeVar

import aiohttp

from yutto._typing import EpisodeData

T = TypeVar("T")


class Extractor:
    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        return (matched, url)

    def match(self, url: str) -> bool:
        raise NotImplementedError

    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        return [await self.extract(session, args)]

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> Optional[Coroutine[Any, Any, Optional[EpisodeData]]]:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        return await self.extract(session, args)

    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[Optional[Coroutine[Any, Any, Optional[EpisodeData]]]]:
        raise NotImplementedError
