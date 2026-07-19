from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from yutto.api.ugc_video import get_ugc_video_list
from yutto.exceptions import MaxRetryError, NoAccessPermissionError, NotFoundError
from yutto.extractor.outcome import BatchResolveOutcome
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

    from yutto.api.ugc_video import UgcVideoList
    from yutto.exceptions import YuttoBaseException
    from yutto.types import AvId
    from yutto.utils.fetcher import FetcherContext
    from yutto.utils.filter import PublicationTimeFilter


async def resolve_ugc_video_lists(
    ctx: FetcherContext,
    client: httpx.AsyncClient,
    avids: list[AvId],
    *,
    publication_time_filter: PublicationTimeFilter,
    on_resolved: Callable[[int, AvId, UgcVideoList | None], Awaitable[None]] | None = None,
) -> BatchResolveOutcome[UgcVideoList]:
    """并发解析一批视频的分 P 列表，结果顺序与 avids 一致

    并发度由 ctx 中已有的 fetch semaphore 控制（Fetcher 的每个请求都会经过 ctx.fetch_guard()），
    这里无需额外限流；被时间过滤或解析失败（NotFoundError / NoAccessPermissionError /
    MaxRetryError）的视频以 None 占位，不会中断整批解析。

    on_resolved 由单一 publisher 串行 await：解析仍然并发，但已完成的结果按完成顺序
    逐个交付（参数为 (index, avid, result)，index 是该 avid 在入参列表中的位置）。
    多个同时就绪的视频不会并发发布、多分 P 视频的事件不会彼此穿插；回调约定在每推送
    一个分集后让出一次控制权（内置提取器均如此），因此事件生产对消费者（如 server
    每连接的 sender）始终可调度，不受同时完成的视频数或单视频分 P 数影响。

    任何未预期的异常（包括回调自身抛出的）会先取消并等待其余子任务再向外抛出——
    函数返回或抛错后不会再有回调或事件发生；单个异常直接抛原始异常，保持稳定错误码。
    """

    async def resolve_one(avid: AvId) -> tuple[UgcVideoList | None, YuttoBaseException | None]:
        try:
            ugc_video_list = await get_ugc_video_list(ctx, client, avid)
            if not publication_time_filter.matches(ugc_video_list["pubdate"]):
                Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                return None, None
            # 在使用 SESSDATA 时，如果不去事先 touch 一下视频链接的话，是无法获取 episode_data 的
            # 至于为什么前面那俩（投稿视频页和番剧页）不需要额外 touch，因为在 get_redirected_url 阶段连接过了呀
            unwrap_fetch_result(await Fetcher.touch_url(ctx, client, avid.to_url()))
            return ugc_video_list, None
        except (NotFoundError, NoAccessPermissionError) as e:
            Logger.error(e.message)
            return None, e
        except MaxRetryError as e:
            Logger.error(f"获取视频 {avid} 信息失败：{e.message}")
            return None, e

    results: list[UgcVideoList | None] = [None] * len(avids)
    failures: list[YuttoBaseException | None] = [None] * len(avids)
    completed: asyncio.Queue[tuple[int, AvId, UgcVideoList | None]] = asyncio.Queue()

    async def resolve_into(index: int, avid: AvId) -> None:
        result, failure = await resolve_one(avid)
        results[index] = result
        failures[index] = failure
        completed.put_nowait((index, avid, result))

    async def publish_completed(deliver: Callable[[int, AvId, UgcVideoList | None], Awaitable[None]]) -> None:
        # 单一 producer：完成一个交付一个，publisher 的每次 await 都给消费者排空队列的机会
        for _ in range(len(avids)):
            index, avid, result = await completed.get()
            await deliver(index, avid, result)

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
    return BatchResolveOutcome(
        results=tuple(results),
        failures=tuple(failure for failure in failures if failure is not None),
    )
