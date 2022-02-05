from typing import TypeVar, Optional, Iterable

T = TypeVar("T")


def filter_none_value(l: Iterable[Optional[T]]) -> Iterable[T]:
    result: Iterable[T] = []
    for item in l:
        if item is not None:
            result.append(item)
    return result
