from __future__ import annotations

import asyncio

import pytest

from yutto.utils.asynclib import race_for_first_success
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


@pytest.mark.parametrize("cancel_race", [False, True])
@as_sync
async def test_race_for_first_success_reaps_operations(cancel_race: bool):
    all_started = asyncio.Event()
    release_winner = asyncio.Event()
    started = 0
    reaped = 0

    async def operation(winner: bool) -> None:
        nonlocal started, reaped
        started += 1
        if started == 2:
            all_started.set()
        try:
            if winner:
                await release_winner.wait()
            else:
                await asyncio.Event().wait()
        except asyncio.CancelledError:
            reaped += 1
            if not cancel_race and not winner:
                raise ValueError("semaphore released too many times") from None
            raise

    task = asyncio.create_task(race_for_first_success([lambda: operation(True), lambda: operation(False)]))
    await all_started.wait()
    if cancel_race:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert reaped == 2
    else:
        release_winner.set()
        assert await task is None
        assert reaped == 1
