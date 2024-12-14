from __future__ import annotations

import base64
import hashlib
import random
import re
import string
import time
import urllib.parse
from typing import TYPE_CHECKING, Any, TypedDict

from yutto._typing import UserInfo
from yutto.utils.asynclib import async_cache
from yutto.utils.fetcher import Fetcher, FetcherContext

if TYPE_CHECKING:
    from httpx import AsyncClient


class WbiImg(TypedDict):
    img_key: str
    sub_key: str


wbi_img_cache: WbiImg | None = None  # Simulate the LocalStorage of the browser
dm_img_str_cache: str = base64.b64encode("".join(random.choices(string.printable, k=random.randint(16, 64))).encode())[:-2].decode()  # fmt: skip
dm_cover_img_str_cache: str = base64.b64encode("".join(random.choices(string.printable, k=random.randint(32, 128))).encode())[:-2].decode()  # fmt: skip


@async_cache(lambda _: "user_info")
async def get_user_info(ctx: FetcherContext, client: AsyncClient) -> UserInfo:
    info_api = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(ctx, client, info_api)
    assert res_json is not None
    res_json_data = res_json.get("data")
    return UserInfo(
        vip_status=res_json_data.get("vipStatus") == 1,  # API 返回的是 int，如果未登录就没这个值
        is_login=res_json_data.get("isLogin"),  # API 返回的是 bool
    )


async def get_wbi_img(ctx: FetcherContext, client: AsyncClient) -> WbiImg:
    global wbi_img_cache
    if wbi_img_cache is not None:
        return wbi_img_cache
    url = "https://api.bilibili.com/x/web-interface/nav"
    res_json = await Fetcher.fetch_json(ctx, client, url)
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
    return "".join([string[idx] for idx in char_indices[:32]])


def encode_wbi(params: dict[str, Any], wbi_img: WbiImg):
    img_key = wbi_img["img_key"]
    sub_key = wbi_img["sub_key"]
    illegal_char_remover = re.compile(r"[!'\(\)*]")

    mixin_key = _get_mixin_key(img_key + sub_key)
    time_stamp = int(time.time())
    params_with_wts = dict(params, wts=time_stamp)
    params_with_dm = {
        **params_with_wts,
        "dm_img_list": "[]",
        "dm_img_str": dm_img_str_cache,
        "dm_cover_img_str": dm_cover_img_str_cache,
    }
    url_encoded_params = urllib.parse.urlencode(
        {
            key: illegal_char_remover.sub("", str(params_with_dm[key]))
            for key in sorted(params_with_dm.keys())
        }
    )  # fmt: skip
    w_rid = hashlib.md5((url_encoded_params + mixin_key).encode()).hexdigest()
    all_params = dict(params_with_dm, w_rid=w_rid)
    return all_params
