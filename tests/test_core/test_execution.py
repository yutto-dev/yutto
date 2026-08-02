from __future__ import annotations

from typing import Any, cast

import pytest

import yutto.__main__ as main_module
from yutto.auth import AuthInfo
from yutto.core.execution import ExecutionScope, RequestExecutionScopeFactory
from yutto.core.request import DownloadRequest
from yutto.types import UserInfo
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


def make_request() -> DownloadRequest:
    return DownloadRequest.model_validate({"source": {"url": "BV1scope"}})


@pytest.mark.parametrize(
    ("fetch_workers", "download_workers", "field"),
    [
        (0, 8, "fetch_workers"),
        (8, 0, "download_workers"),
    ],
)
def test_execution_scope_rejects_non_positive_workers(
    fetch_workers: int,
    download_workers: int,
    field: str,
):
    with pytest.raises(ValueError, match=rf"{field} must be at least 1"):
        ExecutionScope(
            cast("Any", object()),
            fetch_workers=fetch_workers,
            download_workers=download_workers,
        )


@as_sync
async def test_scope_factory_opens_fresh_clients_limiters_and_caches():
    factory = RequestExecutionScopeFactory()
    request = make_request()

    async with factory.open(request) as first_scope:
        first_client = first_scope.client
        first_fetch_limiter = first_scope.fetch_limiter
        assert first_scope.download_workers == 8
        first_scope.user_info_cache = UserInfo(vip_status=True, is_login=True)
        first_scope.wbi_img_cache = {"img_key": "img", "sub_key": "sub"}
        first_scope.touched_urls.add("https://example.com")

    assert first_client.is_closed

    async with factory.open(request) as second_scope:
        assert second_scope.client is not first_client
        assert second_scope.fetch_limiter is not first_fetch_limiter
        assert second_scope.download_workers == 8
        assert second_scope.user_info_cache is None
        assert second_scope.wbi_img_cache is None
        assert second_scope.touched_urls == set()


@as_sync
async def test_scope_factory_closes_client_when_on_open_fails():
    clients: list[Any] = []

    async def fail_on_open(scope: ExecutionScope, request: DownloadRequest) -> None:
        clients.append(scope.client)
        raise RuntimeError("on_open failed")

    factory = RequestExecutionScopeFactory(on_open=fail_on_open)

    with pytest.raises(RuntimeError, match="on_open failed"):
        async with factory.open(make_request()):
            pytest.fail("scope should not be yielded")

    assert len(clients) == 1
    assert clients[0].is_closed


@as_sync
async def test_cli_auth_announcer_deduplicates_effective_credentials(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_by_url: dict[str, AuthInfo | None] = {
        "BV1first": AuthInfo(SESSDATA="member", bili_jct="csrf"),
        "BV1duplicate": AuthInfo(SESSDATA="member", bili_jct="csrf"),
        "BV1other": AuthInfo(SESSDATA="ordinary", bili_jct="other-csrf"),
        "BV1anonymous": None,
        "BV1anonymousAgain": None,
    }
    validation_calls: list[tuple[str | None, str | None]] = []
    vip_messages: list[str] = []
    warning_messages: list[str] = []
    info_messages: list[str] = []

    async def validate(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        assert requirements == {"vip_status": True, "is_login": True}
        credentials = (
            scope.client.cookies.get("SESSDATA"),
            scope.client.cookies.get("bili_jct"),
        )
        validation_calls.append(credentials)
        is_vip = credentials[0] == "member"
        scope.user_info_cache = UserInfo(vip_status=is_vip, is_login=True)
        return is_vip

    monkeypatch.setattr(main_module, "validate_user_info", validate)
    monkeypatch.setattr(main_module.Logger, "custom", lambda message, **_kwargs: vip_messages.append(message))
    monkeypatch.setattr(main_module.Logger, "warning", warning_messages.append)
    monkeypatch.setattr(main_module.Logger, "info", info_messages.append)

    requests = [
        DownloadRequest.model_validate({"source": {"url": url}})
        for url in (
            "BV1first",
            "BV1duplicate",
            "BV1other",
            "BV1anonymous",
            "BV1anonymousAgain",
        )
    ]
    factory = RequestExecutionScopeFactory(
        lambda request: auth_by_url[request.source.url],
        on_open=main_module._CliAuthAnnouncer(),
    )
    caches: list[UserInfo | None] = []

    for request in requests:
        async with factory.open(request) as scope:
            caches.append(scope.user_info_cache)

    assert validation_calls == [("member", "csrf"), ("ordinary", "other-csrf")]
    assert vip_messages == ["成功以大会员身份登录～"]
    assert warning_messages == ["以非大会员身份登录，注意无法下载会员专享剧集喔～"]
    assert info_messages == [
        "未提供登录认证信息，无法下载高清视频、字幕等资源哦～请通过 `--auth` 参数提供认证信息，或者先使用 `yutto auth login` 登录存储认证信息后再下载～"
    ]
    assert caches == [
        UserInfo(vip_status=True, is_login=True),
        None,
        UserInfo(vip_status=False, is_login=True),
        None,
        None,
    ]
