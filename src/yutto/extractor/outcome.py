from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from yutto.exceptions import YuttoBaseException
    from yutto.types import ResolvableEpisode

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ResolveOutcome:
    """Explicit result of one extractor listing operation."""

    items: tuple[ResolvableEpisode, ...] = field(default_factory=tuple)
    failures: tuple[YuttoBaseException, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class BatchResolveOutcome(Generic[T]):
    """Ordered results and expected failures from a concurrent batch lookup."""

    results: tuple[T | None, ...] = field(default_factory=tuple)
    failures: tuple[YuttoBaseException, ...] = field(default_factory=tuple)
