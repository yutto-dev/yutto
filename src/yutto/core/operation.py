from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

OperationEventEmitter = Callable[[str, Mapping[str, object] | None], object]

_event_emitter: ContextVar[OperationEventEmitter | None] = ContextVar("yutto_operation_event_emitter", default=None)


@contextmanager
def bind_operation_event_emitter(emitter: OperationEventEmitter) -> Iterator[None]:
    token = _event_emitter.set(emitter)
    try:
        yield
    finally:
        _event_emitter.reset(token)


def emit_operation_event(kind: str, data: Mapping[str, object] | None = None) -> None:
    emitter = _event_emitter.get()
    if emitter is not None:
        emitter(kind, data)
