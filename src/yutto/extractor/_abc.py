from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from yutto.types import ResolvableEpisode

if TYPE_CHECKING:
    from typing import TypeAlias

    from yutto.core.execution import ExecutionScope
    from yutto.exceptions import YuttoBaseException
    from yutto.extractor.outcome import ResolveOutcome
    from yutto.types import ExtractorOptions

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
        scope: ExecutionScope,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError


class SingleExtractor(Extractor):
    async def __call__(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        return await self.extract(scope, options)

    @abstractmethod
    async def extract(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError


class BatchExtractor(Extractor):
    async def __call__(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        return await self.extract(scope, options, on_item=on_item)

    @abstractmethod
    async def extract(
        self,
        scope: ExecutionScope,
        options: ExtractorOptions,
        *,
        on_item: EpisodeListedCallback | None = None,
    ) -> ResolveOutcome[ResolvableEpisode, YuttoBaseException]:
        raise NotImplementedError
