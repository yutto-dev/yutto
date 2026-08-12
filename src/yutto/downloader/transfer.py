from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto._native import TransferWorkerLimit, wait_for_transfer
from yutto.core.events import DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event, emit_download_report
from yutto.downloader.progressbar import show_progress
from yutto.exceptions import MaxRetryError
from yutto.utils.asynclib import NoSuccessfulResultError, make_coroutine_factory, race_for_first_success
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Any

    from yutto.core.execution import ExecutionScope
    from yutto.downloader.planner import DownloadPlan


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


async def _probe_media_size(scope: ExecutionScope, url: str, mirrors: Iterable[str]) -> int:
    async def probe(candidate: str) -> int:
        size = unwrap_fetch_result(await Fetcher.get_size(scope, candidate))
        if size is None:
            raise MaxRetryError("媒体大小探测未返回长度")
        return size

    create_probe = make_coroutine_factory(probe)
    try:
        return await race_for_first_success(create_probe(candidate) for candidate in (url, *mirrors))
    except NoSuccessfulResultError as error:
        if len(error.exceptions) == 1 and isinstance(error.exceptions[0], MaxRetryError):
            raise error.exceptions[0] from None
        if not error.exceptions:
            raise MaxRetryError("媒体大小探测失败：所有地址均已取消") from error
        raise MaxRetryError(f"媒体大小探测失败：{len(error.exceptions)} 个地址均不可用") from ExceptionGroup(
            "all media size probes failed", error.exceptions
        )


async def download_video_and_audio(scope: ExecutionScope, plan: DownloadPlan) -> None:
    """Download all media through the native Haya transfer core."""
    handles = []
    wait_tasks: list[asyncio.Task[int]] = []
    progress_task: asyncio.Task[None] | None = None
    mirrors_filter = create_mirrors_filter(plan.banned_mirrors_pattern)

    emit_download_event(DownloadStageChanged(name=DownloadStage.DOWNLOADING, item=plan.item))
    emit_download_report("开始下载……")
    try:
        prepared_transfers = []
        for stream, target in (
            (plan.video, plan.paths.video),
            (plan.audio, plan.paths.audio),
        ):
            if stream is None:
                continue
            mirrors = mirrors_filter(list(stream.mirrors))
            size = await _probe_media_size(scope, stream.url, mirrors)
            prepared_transfers.append(([stream.url, *mirrors], target, size))

        total_size = sum(size for _, _, size in prepared_transfers)
        worker_limit = TransferWorkerLimit(scope.download_workers)
        batch_size = 1 if scope.download_workers == 1 else len(prepared_transfers)
        for batch_start in range(0, len(prepared_transfers), batch_size):
            batch_tasks = []
            for sources, target, size in prepared_transfers[batch_start : batch_start + batch_size]:
                handle = scope.session.start_transfer(
                    sources,
                    target,
                    size,
                    overwrite=plan.overwrite,
                    workers=scope.download_workers,
                    block_size=plan.block_size,
                    worker_limit=worker_limit,
                )
                handles.append(handle)
                wait_task = asyncio.create_task(wait_for_transfer(handle))
                wait_tasks.append(wait_task)
                batch_tasks.append(wait_task)

            progress_task = asyncio.create_task(show_progress(handles, total_size, item=plan.item))
            await _wait_for_native_transfers(batch_tasks)
            await progress_task
            progress_task = None
        emit_download_report("下载完成！")
    finally:
        if progress_task is not None:
            if not progress_task.done():
                progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)
        cleanup_task = asyncio.create_task(_cancel_and_reap_native_transfers(handles, wait_tasks))
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            await cleanup_task
            raise


async def _wait_for_native_transfers(wait_tasks: Iterable[asyncio.Task[int]]) -> None:
    try:
        await asyncio.gather(*wait_tasks)
    except RuntimeError as error:
        raise MaxRetryError(f"媒体下载失败：{error}") from error


async def _cancel_and_reap_native_transfers(handles: Iterable[Any], wait_tasks: Iterable[asyncio.Task[int]]) -> None:
    for handle in handles:
        if not handle.done():
            handle.cancel()
    await asyncio.gather(*wait_tasks, return_exceptions=True)


def cleanup_temporary_media(plan: DownloadPlan) -> None:
    if plan.video is not None:
        plan.paths.video.unlink(missing_ok=True)
    if plan.audio is not None:
        plan.paths.audio.unlink(missing_ok=True)
