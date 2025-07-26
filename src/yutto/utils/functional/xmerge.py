from __future__ import annotations

from itertools import chain, zip_longest
from typing import TYPE_CHECKING, TypeVar

from .filter_none_values import filter_none_values

if TYPE_CHECKING:
    from collections.abc import Iterable

T = TypeVar("T")


def xmerge(*multi_list: Iterable[T]) -> Iterable[T]:
    """将多个 list 交错地合并到一个 list

    ### Examples

    ``` python
    multi_list = [
        [1, 2, 3, 4, 5],
        [6, 7, 8],
        [9, 10, 11, 12]
    ]
    xmerge(*multi_list)
    # [1, 6, 9, 2, 7, 10, 3, 8, 11, 4, 12, 5]
    ```
    """
    return filter_none_values(chain(*zip_longest(*multi_list)))
