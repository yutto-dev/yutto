from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from yutto_core._core import (
    HttpError,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
    InvalidUrlError,
    NativeResponse,
    SessionClosedError,
    TransferHandle,
    TransferSnapshot,
    UnsupportedProtocolError,
    YuttoSession,
)

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "HttpError",
    "HttpStatusError",
    "HttpTimeoutError",
    "HttpTransportError",
    "InvalidUrlError",
    "NativeResponse",
    "SessionClosedError",
    "TransferHandle",
    "TransferSnapshot",
    "UnsupportedProtocolError",
    "YuttoSession",
    "wait_for_transfer",
]


async def wait_for_transfer(
    handle: TransferHandle,
    on_snapshot: Callable[[TransferSnapshot], None] | None = None,
    *,
    poll_interval: float = 0.25,
) -> int:
    """Wait without moving media bytes through Python, propagating cancellation."""
    try:
        while not handle.done():
            if on_snapshot is not None:
                on_snapshot(handle.snapshot())
            await asyncio.sleep(poll_interval)
        if on_snapshot is not None:
            on_snapshot(handle.snapshot())
        return handle.result()
    except asyncio.CancelledError:
        handle.cancel()
        while not handle.done():
            await asyncio.sleep(0)
        raise
