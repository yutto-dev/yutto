from __future__ import annotations

from typing import TYPE_CHECKING

from yutto.utils.fetcher import Fetcher

if TYPE_CHECKING:
    import httpx

    from yutto._typing import CId
    from yutto.utils.danmaku import DanmakuData, DanmakuSaveType


async def get_xml_danmaku(client: httpx.AsyncClient, cid: CId) -> str:
    danmaku_api = "http://comment.bilibili.com/{cid}.xml"
    results = await Fetcher.fetch_text(client, danmaku_api.format(cid=cid), encoding="utf-8")
    assert results is not None
    return results


async def get_protobuf_danmaku(client: httpx.AsyncClient, cid: CId, segment_id: int = 1) -> bytes:
    danmaku_api = "http://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index={segment_id}"
    results = await Fetcher.fetch_bin(client, danmaku_api.format(cid=cid, segment_id=segment_id))
    assert results is not None
    return results


async def get_danmaku(
    client: httpx.AsyncClient,
    cid: CId,
    save_type: DanmakuSaveType,
    last_n_segments: int = 2,
) -> DanmakuData:
    # 暂时默认使用 XML 源
    source_type = "xml" if save_type == "xml" or save_type == "ass" else "protobuf"
    danmaku_data: DanmakuData = {
        "source_type": source_type,
        "save_type": save_type,
        "data": [],
    }

    if source_type == "xml":
        danmaku_data["data"].append(await get_xml_danmaku(client, cid))
    else:
        for i in range(1, last_n_segments + 1):
            danmaku_data["data"].append(await get_protobuf_danmaku(client, cid, i))
    return danmaku_data
