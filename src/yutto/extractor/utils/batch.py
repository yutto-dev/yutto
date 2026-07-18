from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from yutto.api.ugc_video import get_ugc_video_list
from yutto.core.operation import report_resolve_failure
from yutto.exceptions import MaxRetryError, NoAccessPermissionError, NotFoundError
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

    from yutto.api.ugc_video import UgcVideoList
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
) -> list[UgcVideoList | None]:
    """并发解析一批视频的分 P 列表，结果顺序与 avids 一致

    并发度由 ctx 中已有的 fetch semaphore 控制（Fetcher 的每个请求都会经过 ctx.fetch_guard()），
    这里无需额外限流；被时间过滤或解析失败（NotFoundError / NoAccessPermissionError /
    MaxRetryError）的视频以 None 占位，不会中断整批解析，其余未预期的异常仍会向外抛出。

    on_resolved 在**每个视频解析完成时**按完成顺序被 await（参数为 (index, avid, result)，
    index 是该 avid 在入参列表中的位置）——提取器用它把已就绪的条目立即推流给前端，
    不必等整批 gather 结束。回调约定在每推送一个分集后让出一次控制权（内置提取器均如此），
    事件生产对消费者（如 server 每连接的 sender）始终可调度，单个超多分 P 的视频
    也不会产生超出发送队列容量的同步 burst。
    """

    async def resolve_one(avid: AvId) -> UgcVideoList | None:
        try:
            ugc_video_list = await get_ugc_video_list(ctx, client, avid)
            if not publication_time_filter.matches(ugc_video_list["pubdate"]):
                Logger.debug(f"因为发布时间为 {ugc_video_list['pubdate']}，跳过 {ugc_video_list['title']}")
                return None
            # 在使用 SESSDATA 时，如果不去事先 touch 一下视频链接的话，是无法获取 episode_data 的
            # 至于为什么前面那俩（投稿视频页和番剧页）不需要额外 touch，因为在 get_redirected_url 阶段连接过了呀
            unwrap_fetch_result(await Fetcher.touch_url(ctx, client, avid.to_url()))
            return ugc_video_list
        except (NotFoundError, NoAccessPermissionError) as e:
            Logger.error(e.message)
            report_resolve_failure(e)
            return None
        except MaxRetryError as e:
            Logger.error(f"获取视频 {avid} 信息失败：{e.message}")
            report_resolve_failure(e)
            return None

    async def resolve_and_notify(index: int, avid: AvId) -> UgcVideoList | None:
        result = await resolve_one(avid)
        if on_resolved is not None:
            await on_resolved(index, avid, result)
        return result

    return await asyncio.gather(*[resolve_and_notify(index, avid) for index, avid in enumerate(avids)])
