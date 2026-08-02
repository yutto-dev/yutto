from __future__ import annotations

import pytest

from yutto.utils.asynclib import make_coroutine_factory
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


@as_sync
async def test_make_coroutine_factory_defers_coroutine_creation():
    created: list[int] = []

    async def resolve(value: int) -> int:
        return value

    def create_coroutine(value: int):
        created.append(value)
        return resolve(value)

    factory = make_coroutine_factory(create_coroutine)(42)
    assert created == []

    coroutine = factory()
    assert created == [42]
    assert await coroutine == 42
