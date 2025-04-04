from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from returns.maybe import Maybe

if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")
U = TypeVar("U")


def map_optional(fn: Callable[[T], U], value: T | None) -> U | None:
    return Maybe.from_optional(value).map(fn).value_or(None)
