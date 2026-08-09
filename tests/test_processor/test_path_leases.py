from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yutto.downloader.path_leases import DownloadPathLeasePool
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


@as_sync
async def test_path_leases_allow_disjoint_jobs_and_serialize_conflicts():
    leases = DownloadPathLeasePool()
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with leases.lease([Path("same")]):
            order.append("first-enter")
            first_entered.set()
            await release_first.wait()
            order.append("first-exit")

    async def conflicting() -> None:
        await first_entered.wait()
        async with leases.lease([Path("same")]):
            order.append("conflicting-enter")

    async def disjoint() -> None:
        await first_entered.wait()
        async with leases.lease([Path("other")]):
            order.append("disjoint-enter")
            release_first.set()

    await asyncio.gather(first(), conflicting(), disjoint())

    assert order == ["first-enter", "disjoint-enter", "first-exit", "conflicting-enter"]
