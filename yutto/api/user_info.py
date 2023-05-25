from __future__ import annotations

import hashlib
import re
import time
import urllib.parse
from typing import Any, TypedDict

from aiohttp import ClientSession

from yutto.utils.fetcher import Fetcher


class WbiImg(TypedDict):
    img_key: str
    sub_key: str


wbi_img_cache: WbiImg | None = None  # Simulate the LocalStorage of the browser


async def is_vip(session: ClientSession) -> bool:
    info_api = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(session, info_api)
    assert res_json is not None
    res_json_data = res_json.get("data")
    if res_json_data.get("vipStatus") == 1:
        return True
    return False


async def get_wbi_img(session: ClientSession) -> WbiImg:
    global wbi_img_cache
    if wbi_img_cache is not None:
        return wbi_img_cache
    url = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(session, url)
    assert res_json is not None
    wbi_img: WbiImg = {
        "img_key": _get_key_from_url(res_json["data"]["wbi_img"]["img_url"]),
        "sub_key": _get_key_from_url(res_json["data"]["wbi_img"]["sub_url"]),
    }
    wbi_img_cache = wbi_img
    return wbi_img


def _get_key_from_url(url: str) -> str:
    return url.split("/")[-1].split(".")[0]


def _get_mixin_key(string: str) -> str:
    char_indices = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5,
        49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55,
        40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57,
        62, 11, 36, 20, 34, 44, 52,
    ]  # fmt: skip
    return "".join(list(map(lambda idx: string[idx], char_indices[:32])))


def encode_wbi(params: dict[str, Any], wbi_img: WbiImg):
    img_key = wbi_img["img_key"]
    sub_key = wbi_img["sub_key"]
    illegal_char_remover = re.compile(r"[!'\(\)*]")

    mixin_key = _get_mixin_key(img_key + sub_key)
    time_stamp = time.time()
    params_with_wts = dict(params, wts=time_stamp)
    url_encoded_params = urllib.parse.urlencode(
        {
            key: illegal_char_remover.sub("", str(params_with_wts[key]))
            for key in sorted(params_with_wts.keys())
        }  # fmt: skip
    )
    w_rid = hashlib.md5((url_encoded_params + mixin_key).encode()).hexdigest()
    all_params = dict(params_with_wts, w_rid=w_rid)
    return all_params
