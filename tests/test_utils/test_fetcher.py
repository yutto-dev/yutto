from __future__ import annotations

import asyncio
import ssl
from typing import Any, Protocol, cast

import pytest

from yutto.utils.fetcher import FetcherContext, create_client, create_sync_client, resolve_proxy


class _HasSSLContext(Protocol):
    _ssl_context: ssl.SSLContext


class _HasPool(Protocol):
    _pool: _HasSSLContext


def _transport_ssl_context(transport: Any) -> ssl.SSLContext:
    # Test helper: inspect httpx's private transport internals to assert TLS policy wiring.
    # If httpx changes `_pool._ssl_context`, this assertion helper will need to be updated too.
    return cast("_HasPool", transport)._pool._ssl_context


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


def test_create_client_keeps_download_tls_verification_disabled():
    client = create_client()
    try:
        transport: Any = client._transport  # pyright: ignore[reportPrivateUsage]
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert not ssl_context.check_hostname
    finally:
        asyncio.run(client.aclose())


def test_create_sync_client_follows_default_download_tls_policy():
    client = create_sync_client()
    try:
        transport: Any = client._transport  # pyright: ignore[reportPrivateUsage]
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert not ssl_context.check_hostname
    finally:
        client.close()


def test_create_sync_client_can_enable_tls_verification():
    client = create_sync_client(verify=True)
    try:
        transport: Any = client._transport  # pyright: ignore[reportPrivateUsage]
        ssl_context = _transport_ssl_context(transport)
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname
    finally:
        client.close()
