from __future__ import annotations

import asyncio

from yutto._core import (
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
) -> int:
    """Wait without moving media bytes through Python, propagating cancellation."""
    try:
        await handle.wait()
        return handle.result()
    except asyncio.CancelledError:
        handle.cancel()
        await handle.wait()
        raise
