from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from yutto.api.ugc_video import UgcVideoList, get_ugc_video_list
from yutto.exceptions import MaxRetryError, NoAccessPermissionError, NotFoundError
from yutto.extractor.outcome import ResolveOutcome
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

    from yutto.exceptions import YuttoBaseException
    from yutto.types import AvId
    from yutto.utils.fetcher import FetcherContext
    from yutto.utils.filter import PublicationTimeFilter

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class IndexedResolveItem(Generic[T]):
    index: int
    source: AvId
    value: T


@dataclass(frozen=True, slots=True)
class IndexedResolveFailure:
    index: int
    source: AvId
    error: YuttoBaseException


@dataclass(frozen=True, slots=True)
class _FilteredResolveItem:
    index: int
    source: AvId


async def resolve_ugc_video_lists(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    avids: list[AvId],
    *,
    publication_time_filter: PublicationTimeFilter,
    on_resolved: Callable[[IndexedResolveItem[UgcVideoList]], Awaitable[None]] | None = None,
) -> ResolveOutcome[IndexedResolveItem[UgcVideoList], IndexedResolveFailure]:
    """并发解析一批视频的分 P 列表，结果顺序与 avids 一致

    并发度由 ctx 中已有的 fetch semaphore 控制（Fetcher 的每个请求都会经过 ctx.fetch_guard()），
    这里无需额外限流；时间过滤项不进入 outcome，预期失败则显式保留输入位置和来源，
    不会中断整批解析。

    on_resolved 由单一 publisher 串行 await：解析仍然并发，但已完成的结果按完成顺序
    逐个交付；每个成功结果携带 avid 及其在入参列表中的位置。
    多个同时就绪的视频不会并发发布、多分 P 视频的事件不会彼此穿插；回调约定在每推送
    一个分集后让出一次控制权（内置提取器均如此），因此事件生产对消费者（如 server
    每连接的 sender）始终可调度，不受同时完成的视频数或单视频分 P 数影响。

    任何未预期的异常（包括回调自身抛出的）会先取消并等待其余子任务再向外抛出——
    函数返回或抛错后不会再有回调或事件发生；单个异常直接抛原始异常，保持稳定错误码。
    """

    async def resolve_one(
        index: int, avid: AvId
    ) -> IndexedResolveItem[UgcVideoList] | IndexedResolveFailure | _FilteredResolveItem:
        try:
            ugc_video_list = await get_ugc_video_list(ctx, client, avid)
            if not publication_time_filter.matches(ugc_video_list["pubdate"]):
                Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                return _FilteredResolveItem(index=index, source=avid)
            # 在使用 SESSDATA 时，如果不去事先 touch 一下视频链接的话，是无法获取 episode_data 的
            # 至于为什么前面那俩（投稿视频页和番剧页）不需要额外 touch，因为在 get_redirected_url 阶段连接过了呀
            unwrap_fetch_result(await Fetcher.touch_url(ctx, client, avid.to_url()))
            return IndexedResolveItem(index=index, source=avid, value=ugc_video_list)
        except (NotFoundError, NoAccessPermissionError) as e:
            Logger.error(e.message)
            return IndexedResolveFailure(index=index, source=avid, error=e)
        except MaxRetryError as e:
            Logger.error(f"获取视频 {avid} 信息失败：{e.message}")
            return IndexedResolveFailure(index=index, source=avid, error=e)

    Completion = IndexedResolveItem[UgcVideoList] | IndexedResolveFailure | _FilteredResolveItem
    completed_by_index: dict[int, Completion] = {}
    completed: asyncio.Queue[Completion] | None = asyncio.Queue() if on_resolved is not None else None

    async def resolve_into(index: int, avid: AvId) -> None:
        result = await resolve_one(index, avid)
        completed_by_index[index] = result
        if completed is not None:
            completed.put_nowait(result)

    async def publish_completed(deliver: Callable[[IndexedResolveItem[UgcVideoList]], Awaitable[None]]) -> None:
        # 单一 producer：完成一个交付一个，publisher 的每次 await 都给消费者排空队列的机会
        assert completed is not None
        for _ in range(len(avids)):
            result = await completed.get()
            if isinstance(result, IndexedResolveItem):
                await deliver(result)

    try:
        async with asyncio.TaskGroup() as task_group:
            for index, avid in enumerate(avids):
                task_group.create_task(resolve_into(index, avid))
            if on_resolved is not None:
                task_group.create_task(publish_completed(on_resolved))
    except ExceptionGroup as error_group:
        # 与先前的 gather 语义对齐：单个失败直接抛原始异常（wire 上保留其稳定错误码），
        # 仅多个子任务同时失败时才抛出 ExceptionGroup
        if len(error_group.exceptions) == 1:
            raise error_group.exceptions[0] from None
        raise
    ordered = tuple(completed_by_index[index] for index in range(len(avids)))
    return ResolveOutcome(
        items=tuple(result for result in ordered if isinstance(result, IndexedResolveItem)),
        failures=tuple(result for result in ordered if isinstance(result, IndexedResolveFailure)),
    )
