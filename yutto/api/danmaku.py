import aiohttp

from yutto.api.types import CId
from yutto.utils.fetcher import Fetcher
from yutto.utils.danmaku import DanmakuData, DanmakuSaveType


async def get_xml_danmaku(session: aiohttp.ClientSession, cid: CId) -> str:
    danmaku_api = "http://comment.bilibili.com/{cid}.xml"
    return await Fetcher.fetch_text(session, danmaku_api.format(cid=cid), encoding="utf-8")


async def get_protobuf_danmaku(session: aiohttp.ClientSession, cid: CId, segment_id: int = 1) -> bytes:
    danmaku_api = "http://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index={segment_id}"
    return await Fetcher.fetch_bin(session, danmaku_api.format(cid=cid, segment_id=segment_id))


async def get_danmaku(
    session: aiohttp.ClientSession,
    cid: CId,
    save_type: DanmakuSaveType,
    last_n_segments: int = 2,
) -> DanmakuData:
    # 暂时默认使用 XML 源
    source_type = "xml" if save_type == "xml" or save_type == "ass" else "protobuf"
    # fmt: off
    danmaku_data: DanmakuData = {
        "source_type": source_type,
        "save_type": save_type,
        "data": []
    }
    # fmt: on

    if source_type == "xml":
        danmaku_data["data"].append(await get_xml_danmaku(session, cid))
    else:
        for i in range(1, last_n_segments + 1):
            danmaku_data["data"].append(await get_protobuf_danmaku(session, cid, i))
    return danmaku_data
