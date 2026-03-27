from __future__ import annotations

import pytest

from yutto.utils.fetcher import FetcherContext, resolve_proxy


def test_resolve_proxy_auto_uses_system_proxy():
    assert resolve_proxy("auto") == (None, True)


def test_resolve_proxy_supports_socks5():
    assert resolve_proxy("socks5://127.0.0.1:1080") == ("socks5://127.0.0.1:1080", False)


def test_fetcher_context_set_proxy_reuses_shared_rules():
    ctx = FetcherContext()

    ctx.set_proxy("https://127.0.0.1:7890")

    assert ctx.proxy == "https://127.0.0.1:7890"
    assert not ctx.trust_env


def test_resolve_proxy_rejects_invalid_scheme():
    with pytest.raises(ValueError, match="proxy 参数值"):
        resolve_proxy("ftp://127.0.0.1:21")
