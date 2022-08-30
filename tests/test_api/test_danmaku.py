from __future__ import annotations

import aiohttp
import pytest

from yutto._typing import CId
from yutto.api.danmaku import get_danmaku, get_protobuf_danmaku, get_xml_danmaku
from yutto.utils.fetcher import Fetcher
from yutto.utils.funcutils import as_sync


@pytest.mark.api
@as_sync
async def test_xml_danmaku():
    cid = CId("144541892")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        danmaku = await get_xml_danmaku(session, cid=cid)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_protobuf_danmaku():
    cid = CId("144541892")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        danmaku = await get_protobuf_danmaku(session, cid=cid, segment_id=1)
        assert len(danmaku) > 0


@pytest.mark.api
@as_sync
async def test_danmaku():
    cid = CId("144541892")
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        danmaku = await get_danmaku(session, cid=cid, save_type="ass", last_n_segments=2)
        assert len(danmaku["data"]) > 0
        assert danmaku["source_type"] == "xml"
        assert danmaku["save_type"] == "ass"
