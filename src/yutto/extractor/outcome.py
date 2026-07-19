from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")
FailureT = TypeVar("FailureT")


@dataclass(frozen=True, slots=True)
class ResolveOutcome(Generic[ItemT, FailureT]):
    """Ordered successes and expected failures from one resolve operation."""

    items: tuple[ItemT, ...] = field(default_factory=tuple)
    failures: tuple[FailureT, ...] = field(default_factory=tuple)
