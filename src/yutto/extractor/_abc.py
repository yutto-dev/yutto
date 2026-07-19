from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from yutto.types import ResolvableEpisode

if TYPE_CHECKING:
    import httpx

    from yutto.extractor.outcome import ResolveOutcome
    from yutto.types import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext

T = TypeVar("T")
EpisodeListedCallback = Callable[[ResolvableEpisode], Awaitable[None]]


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
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        return await self.extract(ctx, client, options, on_item=on_item)

    @abstractmethod
    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        return await self.extract(ctx, client, options, on_item=on_item)

    @abstractmethod
    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome:
        raise NotImplementedError
