from __future__ import annotations

import pytest

from yutto.api.danmaku import get_danmaku, get_protobuf_danmaku_segment, get_xml_danmaku
from yutto.core.execution import ExecutionScope
from yutto.types import AvId, CId
from yutto.utils.fetcher import create_client
from yutto.utils.functional import as_sync


@pytest.mark.api
@as_sync
async def test_xml_danmaku():
    cid = CId("144541892")
    async with create_client() as client:
        scope = ExecutionScope(client)
        danmaku = await get_xml_danmaku(scope, cid=cid)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_protobuf_danmaku():
    cid = CId("144541892")
    async with create_client() as client:
        scope = ExecutionScope(client)
        danmaku = await get_protobuf_danmaku_segment(scope, cid=cid, segment_id=1)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_danmaku():
    cid = CId("144541892")
    avid = AvId("BV1q7411v7Vd")
    async with create_client() as client:
        scope = ExecutionScope(client)
        danmaku = await get_danmaku(scope, cid=cid, avid=avid, save_type="ass")
        assert len(danmaku["data"]) > 0
        assert danmaku["source_type"] == "xml"
        assert danmaku["save_type"] == "ass"
