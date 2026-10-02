from __future__ import annotations

import hashlib
import hmac
import time
from typing import TYPE_CHECKING

from yutto.core.operation import ReportLevel, emit_download_report
from yutto.utils.fetcher import Fetcher, unwrap_fetch_result

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope


# 浏览器匿名身份相关接口与参数，详见 https://github.com/SocialSisterYi/bilibili-API-collect
BILI_SPI_API = "https://api.bilibili.com/x/frontend/finger/spi"
BILI_TICKET_API = "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"
_BILI_TICKET_HMAC_KEY = b"XgwSnGZ1p"
_BILI_TICKET_KEY_ID = "ec02"


async def ensure_web_identity(scope: ExecutionScope) -> None:
    """确保当前会话携带浏览器同款匿名身份 Cookie（buvid3/buvid4/bili_ticket 等）。

    B 站空间等接口会校验设备指纹，缺少这些 Cookie 时容易返回 `-352` 甚至 HTTP 412。
    结果按 scope 缓存，失败时降级为仅尝试访问首页，不阻断后续下载。
    """
    if scope.web_identity_cache is not None:
        return
    async with scope.web_identity_lock:
        if scope.web_identity_cache is not None:
            return
        try:
            cookies = await _bootstrap_web_identity(scope)
        except Exception as error:  # 身份引导失败不应阻断下载
            emit_download_report(f"获取 B 站 Web 身份失败：{error}", ReportLevel.WARNING)
            cookies = {}
        scope.web_identity_cache = cookies


async def _bootstrap_web_identity(scope: ExecutionScope) -> dict[str, str]:
    cookies: dict[str, str] = {}

    try:
        res_json = unwrap_fetch_result(await Fetcher.fetch_json(scope, BILI_SPI_API))
        data = res_json.get("data") or {}
        buvid3 = data.get("b_3")
        buvid4 = data.get("b_4")
    except Exception as error:  # 降级到访问首页获取 buvid3
        emit_download_report(f"获取 buvid 失败，尝试通过首页降级：{error}", ReportLevel.WARNING)
        buvid3 = None
        buvid4 = None
        await Fetcher.touch_url(scope, "https://www.bilibili.com")
        buvid3 = scope.session.cookie("buvid3")

    if buvid3:
        scope.session.set_cookie("buvid3", buvid3)
        cookies["buvid3"] = buvid3
    if buvid4:
        scope.session.set_cookie("buvid4", buvid4)
        cookies["buvid4"] = buvid4

    b_nut = str(int(time.time()))
    scope.session.set_cookie("b_nut", b_nut)
    cookies["b_nut"] = b_nut

    try:
        cookies.update(await _fetch_bili_ticket(scope))
    except Exception as error:  # ticket 可选，缺失时仅降低风控通过率
        emit_download_report(f"获取 bili_ticket 失败，忽略：{error}", ReportLevel.WARNING)

    return cookies


async def _fetch_bili_ticket(scope: ExecutionScope) -> dict[str, str]:
    timestamp = int(time.time())
    hexsign = hmac.new(_BILI_TICKET_HMAC_KEY, f"ts{timestamp}".encode(), hashlib.sha256).hexdigest()
    csrf = scope.session.cookie("bili_jct") or ""
    params = {
        "key_id": _BILI_TICKET_KEY_ID,
        "hexsign": hexsign,
        "context[ts]": str(timestamp),
        "csrf": csrf,
    }
    res_json = unwrap_fetch_result(
        await Fetcher.post_json(
            scope,
            BILI_TICKET_API,
            params=params,
            headers={"Referer": "https://www.bilibili.com/"},
        )
    )
    data = res_json.get("data") or {}
    ticket = data.get("ticket")
    if not ticket:
        raise ValueError(f"GenWebTicket 未返回 ticket：{res_json.get('message')}")
    expires = str(int(data.get("created_at") or timestamp) + int(data.get("ttl") or 0))
    scope.session.set_cookie("bili_ticket", str(ticket))
    scope.session.set_cookie("bili_ticket_expires", expires)
    return {"bili_ticket": str(ticket), "bili_ticket_expires": expires}
