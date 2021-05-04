from urllib.parse import quote, unquote
from typing import Literal, Union

Proxy = Union[Literal["no", "auto"], str]

_proxy: Proxy = "auto"


def gen_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }


def gen_cookies(sessdata: str):
    # 先解码后编码是防止获取到的 SESSDATA 是已经解码后的（包含「,」）
    # 而番剧无法使用解码后的 SESSDATA
    return {"SESSDATA": quote(unquote(sessdata))}


def set_proxy(proxy: Proxy):
    global _proxy
    _proxy = proxy


def gen_trust_env() -> bool:
    if _proxy == "auto":
        return True
    return False


def gen_proxy():
    if _proxy in ["auto", "no"]:
        return None
    else:
        return _proxy
