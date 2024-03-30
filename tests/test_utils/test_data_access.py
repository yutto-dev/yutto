from __future__ import annotations

from typing import Any

import pytest

from yutto.utils.funcutils.data_access import Undefined, data_has_chained_keys

TEST_DATA: list[tuple[Any, list[str], bool]] = [
    # basic
    ({"a": None}, ["a"], True),
    ({"a": Undefined()}, ["a"], False),
    ({"a": Undefined()}, ["a", "b"], False),
    ({"a": 1}, ["a"], True),
    ({"a": 1}, ["a", "b"], False),
    ({"a": 1}, ["b"], False),
    # nested
    ({"a": {"b": 1}}, ["a"], True),
    ({"a": {"b": 1}}, ["a", "b"], True),
    ({"a": {"b": 1}}, ["a", "b", "c"], False),
    ({"a": {"b": 1}}, ["a", "c", "b"], False),
    ({"a": {"b": 1}}, ["0", "1", "2"], False),
    ({"a": {"b": None}}, ["a", "b"], True),
    # not a dict
    (None, [], True),
    (1, [], True),
]


@pytest.mark.parametrize("data, keys, expected", TEST_DATA)
def test_data_has_chained_keys(data: Any, keys: list[str], expected: bool):
    assert data_has_chained_keys(data, keys) == expected
