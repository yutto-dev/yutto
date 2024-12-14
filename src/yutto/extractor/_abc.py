from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    import argparse

    import httpx

    from yutto._typing import EpisodeData
    from yutto.utils.asynclib import CoroutineWrapper
    from yutto.utils.fetcher import FetcherContext

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
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        return [await self.extract(ctx, client, args)]

    @abstractmethod
    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> CoroutineWrapper[EpisodeData | None] | None:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        return await self.extract(ctx, client, args)

    @abstractmethod
    async def extract(
        self, ctx: FetcherContext, client: httpx.AsyncClient, args: argparse.Namespace
    ) -> list[CoroutineWrapper[EpisodeData | None] | None]:
        raise NotImplementedError
