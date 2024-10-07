from __future__ import annotations

from typing import Any, Callable, Generic, NoReturn, Protocol, TypeVar

T = TypeVar("T")
U = TypeVar("U")


class Option(Protocol, Generic[T]):
    def __init__(self): ...

    def is_some(self) -> bool: ...

    def is_none(self) -> bool: ...

    def map(self, fn: Callable[[T], Any]) -> Option[Any]: ...

    def unwrap(self) -> T: ...

    def unwrap_or(self, default: T) -> T:
        return self.unwrap() if self.is_some() else default

    @staticmethod
    def from_optional(value: U | None) -> Option[U]:
        return Some(value) if value is not None else None_()

    def to_optional(self) -> T | None:
        return self.unwrap() if self.is_some() else None

    def __bool__(self) -> bool:
        return self.is_some()


class Some(Option[T]):
    value: T

    def __init__(self, value: T):
        self.value = value

    def is_some(self) -> bool:
        return True

    def is_none(self) -> bool:
        return False

    def map(self, fn: Callable[[T], U]) -> Option[U]:
        return Some(fn(self.value))

    def unwrap(self) -> T:
        return self.value


class None_(Option[Any]):
    def __init__(self): ...

    def is_some(self) -> bool:
        return False

    def is_none(self) -> bool:
        return True

    def map(self, fn: Callable[[Any], Any]) -> Option[Any]:
        return None_()

    def unwrap(self) -> NoReturn:
        raise ValueError("Cannot unwrap None_ object")


def map_some(fn: Callable[[T], U], value: T | None) -> U | None:
    return Option.from_optional(value).map(fn).to_optional()
