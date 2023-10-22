from __future__ import annotations

import argparse
from abc import ABCMeta, abstractmethod
from typing import TypeVar

import aiohttp

from yutto._typing import EpisodeData
from yutto.utils.asynclib import CoroutineWrapper

T = TypeVar("T")


class Extractor(metaclass=ABCMeta):
    def resolve_shortcut(self, id: str) -> tuple[bool, str]:
        matched = False
        url = id
        return (matched, url)

    @abstractmethod
    def match(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        return [await self.extract(session, args)]

    @abstractmethod
    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> CoroutineWrapper[EpisodeData | None] | None:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        return await self.extract(session, args)

    @abstractmethod
    async def extract(
        self, session: aiohttp.ClientSession, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        raise NotImplementedError
