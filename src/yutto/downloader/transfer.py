from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from yutto.core.events import DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event, emit_download_report
from yutto.downloader.progressbar import show_native_progress, show_progress
from yutto.exceptions import MaxRetryError
from yutto.utils.asynclib import NoSuccessfulResultError, make_coroutine_factory, race_for_first_success
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


async def _probe_media_size(
    scope: ExecutionScope,
    url: str,
    mirrors: Iterable[str],
    *,
    require_known: bool = False,
) -> int | None:
    async def probe(candidate: str) -> int | None:
        size = unwrap_fetch_result(await Fetcher.get_size(scope, candidate))
        if require_known and size is None:
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
    """Download media with the backend selected explicitly by the plan."""
    if plan.download_backend == "rust":
        await _download_video_and_audio_rust(scope, plan)
    else:
        await _download_video_and_audio_python(scope, plan)


async def _download_video_and_audio_python(scope: ExecutionScope, plan: DownloadPlan) -> None:
    """Download the media inputs described by a plan."""
    buffers: list[AsyncFileBuffer | None] = [None, None]
    sizes: list[int | None] = [None, None]
    coroutine_factories_list: list[list[Callable[[], Coroutine[Any, Any, None]]]] = []
    lifecycle_started = False
    mirrors_filter = create_mirrors_filter(plan.banned_mirrors_pattern)

    defer_download_file = make_coroutine_factory(Fetcher.download_file_with_offset)
    defer_progress = make_coroutine_factory(show_progress)

    emit_download_event(DownloadStageChanged(name=DownloadStage.DOWNLOADING, item=plan.item))
    emit_download_report("开始下载……")
    try:
        if plan.video is not None:
            video_size = await _probe_media_size(
                scope,
                plan.video.url,
                mirrors_filter(list(plan.video.mirrors)),
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
            audio_size = await _probe_media_size(
                scope,
                plan.audio.url,
                mirrors_filter(list(plan.audio.mirrors)),
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


async def _download_video_and_audio_rust(scope: ExecutionScope, plan: DownloadPlan) -> None:
    try:
        from yutto_core import start_transfer, wait_for_transfer
    except ImportError as error:
        raise RuntimeError("Rust 下载后端不可用，请安装带有 yutto-core 的 yutto 后再重试") from error

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
            size = await _probe_media_size(scope, stream.url, mirrors, require_known=True)
            assert size is not None
            prepared_transfers.append(([stream.url, *mirrors], target, size))

        completed_transfers = 0
        total_size = sum(size for _, _, size in prepared_transfers)
        for worker_batch in _allocate_native_worker_batches(scope.download_workers, len(prepared_transfers)):
            batch_tasks = []
            for workers in worker_batch:
                sources, target, size = prepared_transfers[completed_transfers]
                completed_transfers += 1
                handle = start_transfer(
                    sources,
                    target,
                    size,
                    overwrite=plan.overwrite,
                    headers=_native_http_headers(scope),
                    source_headers=_native_source_headers(scope, sources),
                    proxy=scope.proxy,
                    use_system_proxy=scope.trust_env,
                    # The current httpx media path is configured with verify=False.
                    accept_invalid_certs=True,
                    workers=workers,
                    block_size=plan.block_size,
                )
                handles.append(handle)
                wait_task = asyncio.create_task(wait_for_transfer(handle, poll_interval=0.05))
                wait_tasks.append(wait_task)
                batch_tasks.append(wait_task)

            progress_task = asyncio.create_task(show_native_progress(handles, total_size))
            await asyncio.gather(*batch_tasks)
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


def _allocate_native_worker_batches(total_workers: int, transfer_count: int) -> list[list[int]]:
    batches = []
    remaining = transfer_count
    while remaining:
        batch_size = min(total_workers, remaining)
        workers_per_transfer, extra_workers = divmod(total_workers, batch_size)
        batches.append([workers_per_transfer + (index < extra_workers) for index in range(batch_size)])
        remaining -= batch_size
    return batches


async def _cancel_and_reap_native_transfers(handles: Iterable[Any], wait_tasks: Iterable[asyncio.Task[int]]) -> None:
    handle_list = list(handles)
    for handle in handle_list:
        if not handle.done():
            handle.cancel()
    await asyncio.gather(*wait_tasks, return_exceptions=True)


def _native_http_headers(scope: ExecutionScope) -> dict[str, str]:
    headers = dict(scope.client.headers.multi_items())
    headers.pop("cookie", None)
    return headers


def _native_source_headers(scope: ExecutionScope, sources: Iterable[str]) -> list[dict[str, str]]:
    source_headers = []
    for source in sources:
        cookie = scope.client.build_request("GET", source).headers.get("cookie")
        source_headers.append({"cookie": cookie} if cookie is not None else {})
    return source_headers


def cleanup_temporary_media(plan: DownloadPlan) -> None:
    if plan.video is not None:
        plan.paths.video.unlink(missing_ok=True)
    if plan.audio is not None:
        plan.paths.audio.unlink(missing_ok=True)
