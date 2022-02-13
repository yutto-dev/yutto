from typing import TypeVar, Optional, Iterable

T = TypeVar("T")


def filter_none_value(l: Iterable[Optional[T]]) -> Iterable[T]:
    """移除列表（迭代器）中的 None

    Examples:
        .. code-block:: python

            l1 = [1, 2, 3, None, 5, None, 7]
            l2 = filter_none_value(l1)
            assert l2 == [1, 2, 3, 5, 7]
    """
    result: Iterable[T] = []
    for item in l:
        if item is not None:
            result.append(item)
    return result
