from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from biliass import get_danmaku_meta_size

from yutto.api.user_info import get_user_info
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.types import AvId, CId
    from yutto.utils.danmaku import DanmakuData, DanmakuSaveType


async def get_xml_danmaku(scope: ExecutionScope, cid: CId) -> str:
    danmaku_api = "http://comment.bilibili.com/{cid}.xml"
    results = unwrap_fetch_result(await Fetcher.fetch_text(scope, danmaku_api.format(cid=cid), encoding="utf-8"))
    assert results is not None
    return results


async def get_protobuf_danmaku_segment(scope: ExecutionScope, cid: CId, segment_id: int = 1) -> bytes:
    danmaku_api = "http://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index={segment_id}"
    results = unwrap_fetch_result(await Fetcher.fetch_bin(scope, danmaku_api.format(cid=cid, segment_id=segment_id)))
    assert results is not None
    return results


async def get_protobuf_danmaku(scope: ExecutionScope, avid: AvId, cid: CId) -> list[bytes]:
    danmaku_meta_api = "https://api.bilibili.com/x/v2/dm/web/view?type=1&oid={cid}&pid={aid}"
    aid = avid.as_aid()
    meta_results = unwrap_fetch_result(await Fetcher.fetch_bin(scope, danmaku_meta_api.format(cid=cid, aid=aid.value)))
    assert meta_results is not None
    size = get_danmaku_meta_size(meta_results)

    results = await asyncio.gather(
        *[get_protobuf_danmaku_segment(scope, cid, segment_id) for segment_id in range(1, size + 1)]
    )
    return results


async def get_danmaku(
    scope: ExecutionScope,
    cid: CId,
    avid: AvId,
    save_type: DanmakuSaveType,
) -> DanmakuData:
    # 在已经登录的情况下，使用 protobuf，因为未登录时 protobuf 弹幕会少非常多
    source_type = "xml" if save_type == "xml" or not (await get_user_info(scope))["is_login"] else "protobuf"
    danmaku_data: DanmakuData = {
        "source_type": source_type,
        "save_type": save_type,
        "data": [],
    }

    if source_type == "xml":
        danmaku_data["data"].append(await get_xml_danmaku(scope, cid))
    else:
        danmaku_data["data"].extend(await get_protobuf_danmaku(scope, avid, cid))
    return danmaku_data
