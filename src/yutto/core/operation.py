from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterator

    from yutto.core.events import DownloadEvent, DownloadEventSink

ReportLevel: TypeAlias = Literal["debug", "error", "info", "plain", "warning"]
ReportColor: TypeAlias = Literal["blue", "green", "magenta"]
ReportSink: TypeAlias = Callable[[str, ReportLevel, str | None, ReportColor | None], None]

_event_sink: ContextVar[DownloadEventSink | None] = ContextVar("yutto_download_event_sink", default=None)
_report_sink: ContextVar[ReportSink | None] = ContextVar("yutto_download_report_sink", default=None)


@contextmanager
def bind_download_event_sink(sink: DownloadEventSink) -> Iterator[None]:
    token = _event_sink.set(sink)
    try:
        yield
    finally:
        _event_sink.reset(token)


@contextmanager
def bind_download_report_sink(sink: ReportSink) -> Iterator[None]:
    token = _report_sink.set(sink)
    try:
        yield
    finally:
        _report_sink.reset(token)


def emit_download_event(event: DownloadEvent) -> None:
    sink = _event_sink.get()
    if sink is not None:
        sink.emit(event)


def emit_download_report(
    message: str,
    level: ReportLevel = "info",
    badge: str | None = None,
    color: ReportColor | None = None,
) -> None:
    sink = _report_sink.get()
    if sink is not None:
        sink(message, level, badge, color)
