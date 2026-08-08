from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable
    from pathlib import Path


class DownloadPathLeasePool:
    """Serialize downloads whose final or temporary artifact namespaces overlap."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._leased: set[Path] = set()

    @asynccontextmanager
    async def lease(self, paths: Iterable[Path]) -> AsyncIterator[None]:
        keys = frozenset(path.resolve() for path in paths)
        if not keys:
            raise ValueError("at least one path lease key is required")

        async with self._condition:
            await self._condition.wait_for(lambda: self._leased.isdisjoint(keys))
            self._leased.update(keys)
        try:
            yield
        finally:
            async with self._condition:
                self._leased.difference_update(keys)
                self._condition.notify_all()
