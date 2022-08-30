from __future__ import annotations

from aiohttp import ClientSession

from yutto.utils.fetcher import Fetcher


async def is_vip(session: ClientSession) -> bool:
    info_api = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(session, info_api)
    assert res_json is not None
    res_json_data = res_json.get("data")
    if res_json_data.get("vipStatus") == 1:
        return True
    return False
