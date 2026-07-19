from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from yutto.types import ResolvableEpisode

if TYPE_CHECKING:
    from typing import TypeAlias

    import httpx

    from yutto.exceptions import YuttoBaseException
    from yutto.extractor.outcome import ResolveOutcome
    from yutto.types import ExtractorOptions
    from yutto.utils.fetcher import FetcherContext

    ExtractorResolveOutcome: TypeAlias = ResolveOutcome[ResolvableEpisode, YuttoBaseException]

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
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        return await self.extract(ctx, client, options)

    @abstractmethod
    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        return await self.extract(ctx, client, options)

    @abstractmethod
    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError


class StreamingBatchExtractor(BatchExtractor):
    async def __call__(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        return await self.extract(ctx, client, options, on_item=on_item)

    @abstractmethod
    async def extract(
        self,
        ctx: FetcherContext,
        client: httpx.AsyncClient,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError
