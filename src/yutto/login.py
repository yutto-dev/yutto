from __future__ import annotations

import time
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import segno

from yutto.api.user_info import get_user_info
from yutto.auth import AuthInfo, resolve_auth_file, save_auth
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import FetcherContext, create_client

QR_GENERATE_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

# 这些状态码来自 B 站二维码登录返回 data.code
QR_STATUS_NOT_SCANNED = 86101
QR_STATUS_SCANNED = 86090
QR_STATUS_EXPIRED = 86038
QR_STATUS_CONFIRMED = 0


def run_login(args: Any):
    proxy, trust_env = _resolve_proxy(args.proxy)
    client = httpx.Client(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com",
        },
        trust_env=trust_env,
        proxy=proxy,
        follow_redirects=True,
        timeout=10,
    )

    try:
        qr_login_url, qr_key = generate_qr_login(client)
        show_qr_code(qr_login_url, args.mode)
        Logger.info("请使用哔哩哔哩 App 扫码并确认登录")
        redirect_url = poll_qr_login(client, qr_key, timeout=args.timeout, poll_interval=args.poll_interval)
        result_url, sessdata, bili_jct = complete_login(client, redirect_url)
        if sessdata is None:
            raise ValueError("登录成功但未提取到 SESSDATA")

        auth_file = resolve_auth_file(args)
        save_auth(auth_file, args.auth_profile, sessdata, bili_jct)
        auth = AuthInfo(SESSDATA=sessdata, bili_jct=bili_jct)
        if validate_login(auth, proxy=proxy, trust_env=trust_env):
            Logger.info(
                f"登录成功，已写入认证文件：{auth_file}（profile: {args.auth_profile}，url: {sanitize_url_for_log(result_url)}）"
            )
        else:
            Logger.warning(
                f"SESSDATA 已写入认证文件，但登录状态校验失败，请稍后重试。文件：{auth_file}（profile: {args.auth_profile}）"
            )
    finally:
        client.close()


def _resolve_proxy(proxy: str) -> tuple[str | None, bool]:
    if proxy == "auto":
        return None, True
    if proxy == "no":
        return None, False
    parsed = urlparse(proxy)
    allowed_schemes = {"http", "https", "socks5", "socks5h"}
    if not parsed.scheme or parsed.scheme not in allowed_schemes:
        raise ValueError(f"proxy 参数值（{proxy}）错误啦！")
    return proxy, False


def sanitize_url_for_log(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def generate_qr_login(client: httpx.Client) -> tuple[str, str]:
    payload = request_json(client, QR_GENERATE_API, params={"source": "main-fe-header"})
    code = payload.get("code")
    if not isinstance(code, int) or code != 0:
        raise ValueError(f"获取登录二维码失败：{payload}")
    data_any = payload.get("data")
    if not isinstance(data_any, dict):
        raise ValueError(f"获取登录二维码失败，返回值异常：{payload}")
    data = cast("dict[str, Any]", data_any)
    login_url = data.get("url")
    qrcode_key = data.get("qrcode_key")
    if not isinstance(login_url, str) or not isinstance(qrcode_key, str):
        raise ValueError(f"获取登录二维码失败，缺少 url 或 qrcode_key：{payload}")
    return login_url, qrcode_key


def show_qr_code(url: str, mode: str):
    qr = segno.make(url)
    if mode == "web":
        try:
            # segno 的 stubs 会携带 Unknown，这里通过 Any 调用避免 pyright 噪音
            cast("Any", qr).show()
            return
        except Exception as e:
            Logger.warning(f"web 模式显示二维码失败，将回退到终端输出：{e}")
    qr.terminal(compact=True)


def poll_qr_login(client: httpx.Client, qrcode_key: str, *, timeout: int, poll_interval: float) -> str:
    deadline = time.monotonic() + timeout
    last_status: int | None = None
    while time.monotonic() < deadline:
        payload = request_json(client, QR_POLL_API, params={"qrcode_key": qrcode_key, "source": "main-fe-header"})
        code = payload.get("code")
        if not isinstance(code, int) or code != 0:
            raise ValueError(f"轮询登录状态失败：{payload}")

        data_any = payload.get("data")
        if not isinstance(data_any, dict):
            raise ValueError(f"轮询登录状态失败，返回值异常：{payload}")
        data = cast("dict[str, Any]", data_any)
        status = data.get("code")
        if not isinstance(status, int):
            raise ValueError(f"轮询登录状态失败，缺少状态码：{payload}")

        if status != last_status:
            if status == QR_STATUS_NOT_SCANNED:
                Logger.info("二维码待扫描")
            elif status == QR_STATUS_SCANNED:
                Logger.info("已扫码，请在 App 内确认登录")
            elif status == QR_STATUS_EXPIRED:
                raise TimeoutError("二维码已过期，请重新执行 login")
            last_status = status

        if status == QR_STATUS_CONFIRMED:
            redirect_url = data.get("url")
            if not isinstance(redirect_url, str):
                raise ValueError(f"登录成功但未返回跳转链接：{payload}")
            return redirect_url

        time.sleep(poll_interval)
    raise TimeoutError(f"登录超时（>{timeout} 秒），请重试")


def request_json(client: httpx.Client, url: str, *, params: dict[str, str]) -> dict[str, Any]:
    resp = client.get(url, params=params)
    resp.raise_for_status()
    payload_any = resp.json()
    if not isinstance(payload_any, dict):
        raise ValueError(f"接口返回 JSON 结构异常：{url}")
    return cast("dict[str, Any]", payload_any)


def extract_sessdata(redirect_url: str) -> str | None:
    query = parse_qs(urlparse(redirect_url).query)
    values = query.get("SESSDATA")
    if not values:
        return None
    return unquote(values[0])


def extract_bili_jct(redirect_url: str) -> str | None:
    query = parse_qs(urlparse(redirect_url).query)
    values = query.get("bili_jct")
    if not values:
        return None
    return unquote(values[0])


def complete_login(client: httpx.Client, redirect_url: str) -> tuple[str, str | None, str | None]:
    # 登录成功后返回的 URL 需要真正请求一次，才能让 cookie jar 更新到最新值
    final_url = redirect_url
    try:
        resp = client.get(redirect_url)
        final_url = str(resp.url)
    except Exception as e:
        Logger.warning(f"请求登录确认 URL 失败，将尝试从返回 URL 提取 cookies：{e}")

    sessdata = get_cookie_value(client.cookies, "SESSDATA")
    bili_jct = get_cookie_value(client.cookies, "bili_jct")

    if not sessdata:
        sessdata = extract_sessdata(final_url) or extract_sessdata(redirect_url)
    if not bili_jct:
        bili_jct = extract_bili_jct(final_url) or extract_bili_jct(redirect_url)

    return final_url, sessdata, bili_jct


def get_cookie_value(cookies: httpx.Cookies, name: str) -> str | None:
    try:
        return cookies.get(name)
    except httpx.CookieConflict:
        # 同名 cookie 可能存在于多个域名，优先取 bilibili 主域下的值
        candidates: list[tuple[str, str]] = []
        for cookie in cookies.jar:
            if cookie.name == name and cookie.value is not None:
                candidates.append((cookie.domain, cookie.value))
        domain_priority = [".bilibili.com", "bilibili.com", ".passport.bilibili.com", "passport.bilibili.com"]
        for target_domain in domain_priority:
            for domain, value in candidates:
                if domain == target_domain:
                    return value
        if candidates:
            return candidates[0][1]
        return None


def validate_login(auth: AuthInfo, *, proxy: str | None, trust_env: bool) -> bool:
    ctx = FetcherContext(proxy=proxy, trust_env=trust_env)
    ctx.set_auth_info(auth)
    try:
        import asyncio

        async def _validate() -> bool:
            async with create_client(cookies=ctx.cookies, proxy=ctx.proxy, trust_env=ctx.trust_env) as client:
                user_info = await get_user_info(ctx, client)
                return user_info["is_login"]

        return asyncio.run(_validate())
    except Exception:
        return False
