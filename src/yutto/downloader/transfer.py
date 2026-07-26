from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.core.events import DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event, emit_download_report
from yutto.downloader.progressbar import show_progress
from yutto.utils.asynclib import first_successful_with_check, make_coroutine_factory
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result
from yutto.utils.file_buffer import AsyncFileBuffer
from yutto.utils.functional import filter_none_values, xmerge

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable
    from typing import Any, Protocol

    from yutto.core.execution import ExecutionScope
    from yutto.downloader.planner import DownloadPlan

    class _DownloadBuffer(Protocol):
        def ensure_flushed(self) -> None: ...

        async def close(self) -> None: ...


def slice_blocks(start: int, total_size: int | None, block_size: int | None = None) -> list[tuple[int, int | None]]:
    """Generate the (offset, byte count) ranges used by parallel downloads."""
    if total_size is None:
        return [(0, None)]
    assert start <= total_size, f"起始地址（{start}）大于总地址（{total_size}）"
    remaining = total_size - start
    if remaining == 0:
        return []
    if block_size is None:
        return [(start, remaining)]
    return [(offset, min(block_size, total_size - offset)) for offset in range(start, total_size, block_size)]


def create_mirrors_filter(banned_mirrors_pattern: str | None) -> Callable[[list[str]], list[str]]:
    mirror_filter: Callable[[str], bool]
    if banned_mirrors_pattern is None:
        mirror_filter = lambda _: True  # noqa: E731
    else:
        regex_banned_pattern = re.compile(banned_mirrors_pattern)
        mirror_filter = lambda url: not regex_banned_pattern.search(url)  # noqa: E731

    def mirrors_filter(mirrors: list[str]) -> list[str]:
        return list(filter(mirror_filter, mirrors))

    return mirrors_filter


async def _run_download_lifecycle(
    coroutine_factories: Iterable[Callable[[], Coroutine[Any, Any, None]]],
    buffers: Iterable[_DownloadBuffer],
) -> None:
    """Create transfer tasks lazily, then reap tasks and buffers together."""
    tasks: list[asyncio.Task[None]] = []
    buffer_list = list(buffers)
    try:
        for create_coroutine in coroutine_factories:
            coroutine = create_coroutine()
            try:
                tasks.append(asyncio.create_task(coroutine))
            except BaseException:
                coroutine.close()
                raise
        await asyncio.gather(*tasks)
        for buffer in buffer_list:
            buffer.ensure_flushed()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for buffer in buffer_list:
            await buffer.close()


async def download_video_and_audio(scope: ExecutionScope, plan: DownloadPlan) -> None:
    """Download the media inputs described by a plan."""
    buffers: list[AsyncFileBuffer | None] = [None, None]
    sizes: list[int | None] = [None, None]
    coroutine_factories_list: list[list[Callable[[], Coroutine[Any, Any, None]]]] = []
    lifecycle_started = False
    mirrors_filter = create_mirrors_filter(plan.banned_mirrors_pattern)

    async def get_size(url: str) -> int | None:
        return unwrap_fetch_result(await Fetcher.get_size(scope, url))

    defer_download_file = make_coroutine_factory(Fetcher.download_file_with_offset)
    defer_progress = make_coroutine_factory(show_progress)

    emit_download_event(DownloadStageChanged(name=DownloadStage.DOWNLOADING, item=plan.item))
    emit_download_report("开始下载……")
    try:
        if plan.video is not None:
            video_size = await first_successful_with_check(
                [get_size(url) for url in [plan.video.url, *mirrors_filter(list(plan.video.mirrors))]]
            )
            video_buffer = await AsyncFileBuffer.open(
                plan.paths.video,
                overwrite=plan.overwrite or video_size is None,
            )
            buffers[0] = video_buffer
            sizes[0] = video_size
            coroutine_factories_list.append(
                [
                    defer_download_file(
                        scope,
                        plan.video.url,
                        mirrors_filter(list(plan.video.mirrors)),
                        video_buffer,
                        offset,
                        block_size,
                    )
                    for offset, block_size in slice_blocks(
                        video_buffer.written_size,
                        video_size,
                        plan.block_size,
                    )
                ]
            )

        if plan.audio is not None:
            audio_size = await first_successful_with_check(
                [get_size(url) for url in [plan.audio.url, *mirrors_filter(list(plan.audio.mirrors))]]
            )
            audio_buffer = await AsyncFileBuffer.open(
                plan.paths.audio,
                overwrite=plan.overwrite or audio_size is None,
            )
            buffers[1] = audio_buffer
            sizes[1] = audio_size
            coroutine_factories_list.append(
                [
                    defer_download_file(
                        scope,
                        plan.audio.url,
                        mirrors_filter(list(plan.audio.mirrors)),
                        audio_buffer,
                        offset,
                        block_size,
                    )
                    for offset, block_size in slice_blocks(
                        audio_buffer.written_size,
                        audio_size,
                        plan.block_size,
                    )
                ]
            )

        coroutine_factories = list(xmerge(*coroutine_factories_list))
        media_buffers = filter_none_values(buffers)
        known_sizes = filter_none_values(sizes)
        if len(known_sizes) == len(media_buffers):
            coroutine_factories.insert(0, defer_progress(media_buffers, sum(known_sizes)))
        lifecycle_started = True
        await _run_download_lifecycle(coroutine_factories, media_buffers)
        emit_download_report("下载完成！")
    finally:
        if not lifecycle_started:
            for buffer in filter_none_values(buffers):
                await buffer.close()


def cleanup_temporary_media(plan: DownloadPlan) -> None:
    if plan.video is not None:
        plan.paths.video.unlink(missing_ok=True)
    if plan.audio is not None:
        plan.paths.audio.unlink(missing_ok=True)
