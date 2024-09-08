from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable

T = TypeVar("T")


def filter_none_value(list_contains_some_none: Iterable[T | None]) -> Iterable[T]:
    """移除列表（迭代器）中的 None

    ### Examples

    ``` python
    l1 = [1, 2, 3, None, 5, None, 7]
    l2 = filter_none_value(l1)
    assert l2 == [1, 2, 3, 5, 7]
    ```
    """
    result: Iterable[T] = []
    for item in list_contains_some_none:
        if item is not None:
            result.append(item)
    return result
