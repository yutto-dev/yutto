from __future__ import annotations

from typing import Any


class Undefined: ...


def data_has_chained_keys(data: Any, keys: list[str]) -> bool:
    if isinstance(data, Undefined):
        return False
    if not keys:
        return True
    if not isinstance(data, dict):
        return False
    key, *remaining_keys = keys
    return data_has_chained_keys(data.get(key, Undefined()), remaining_keys)  # type: ignore
