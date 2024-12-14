from __future__ import annotations

import pytest

from yutto._typing import AvId, CId
from yutto.api.danmaku import get_danmaku, get_protobuf_danmaku_segment, get_xml_danmaku
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
async def test_xml_danmaku():
    cid = CId("144541892")
    ctx = FetcherContext()
    async with create_client() as client:
        danmaku = await get_xml_danmaku(ctx, client, cid=cid)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_protobuf_danmaku():
    cid = CId("144541892")
    ctx = FetcherContext()
    async with create_client() as client:
        danmaku = await get_protobuf_danmaku_segment(ctx, client, cid=cid, segment_id=1)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_danmaku():
    cid = CId("144541892")
    avid = AvId("BV1q7411v7Vd")
    ctx = FetcherContext()
    async with create_client() as client:
        danmaku = await get_danmaku(ctx, client, cid=cid, avid=avid, save_type="ass")
        assert len(danmaku["data"]) > 0
        assert danmaku["source_type"] == "xml"
        assert danmaku["save_type"] == "ass"
