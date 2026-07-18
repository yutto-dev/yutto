from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from yutto.core.events import DownloadEvent, DownloadEventSink
    from yutto.exceptions import YuttoBaseException
    from yutto.types import ResolvableEpisode

_event_sink: ContextVar[DownloadEventSink | None] = ContextVar("yutto_download_event_sink", default=None)
_resolve_failures: ContextVar[list[YuttoBaseException] | None] = ContextVar("yutto_resolve_failures", default=None)

# resolve 模式的逐条列举钩子：batch 提取器在每个视频解析完成时把它的分集推给
# 钩子，长列表就能边解析边在前端出现，而不是全部完成后一次性倾倒。未绑定时
# （下载路径、未流式化的提取器）保持原有整批行为。
_episode_listed_hook: ContextVar[Callable[[ResolvableEpisode], None] | None] = ContextVar(
    "yutto_episode_listed_hook", default=None
)


@contextmanager
def bind_download_event_sink(sink: DownloadEventSink) -> Iterator[None]:
    token = _event_sink.set(sink)
    try:
        yield
    finally:
        _event_sink.reset(token)


def emit_download_event(event: DownloadEvent) -> None:
    sink = _event_sink.get()
    if sink is not None:
        sink.emit(event)


@contextmanager
def collect_resolve_failures() -> Iterator[list[YuttoBaseException]]:
    """采集本次解析过程中 extractor 上报的预期内失败"""
    failures: list[YuttoBaseException] = []
    token = _resolve_failures.set(failures)
    try:
        yield failures
    finally:
        _resolve_failures.reset(token)


def report_resolve_failure(error: YuttoBaseException) -> None:
    """extractor 在把预期失败吞成 None / 空列表之前上报结构化原因。

    仅在解析路径（collect_resolve_failures 绑定期间）生效；下载路径为 no-op，
    行为不受影响。
    """
    failures = _resolve_failures.get()
    if failures is not None:
        failures.append(error)


@contextmanager
def bind_episode_listed_hook(hook: Callable[[ResolvableEpisode], None]) -> Iterator[None]:
    token = _episode_listed_hook.set(hook)
    try:
        yield
    finally:
        _episode_listed_hook.reset(token)


def notify_episode_listed(episode: ResolvableEpisode) -> None:
    hook = _episode_listed_hook.get()
    if hook is not None:
        hook(episode)
