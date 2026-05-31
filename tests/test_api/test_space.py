from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
from returns.result import Failure, Success

from yutto.api import space as space_module
from yutto.api.space import (
    get_all_favourites,
    get_favourite_avids,
    get_favourite_info,
    get_medialist_avids,
    get_medialist_title,
    get_user_name,
    get_user_space_all_videos_avids,
)
from yutto.types import AId, BvId, FId, MId, SeriesId
from yutto.utils.fetcher import Fetcher, FetcherContext, create_client
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from yutto.utils.fetcher import FetcherContext as FetcherContextType


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_space_all_videos_avids():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        all_avid = await get_user_space_all_videos_avids(ctx, client, mid=mid)
        assert len(all_avid) > 0
        assert AId("371660125") in all_avid or BvId("BV1vZ4y1M7mQ") in all_avid


@pytest.mark.api
@as_sync
async def test_get_user_space_all_videos_avids_filters_with_space_pubdate(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    async def fake_get_wbi_img(ctx: FetcherContextType, client: Any) -> object:
        return object()

    def fake_encode_wbi(params: dict[str, Any], wbi_img: object) -> dict[str, Any]:
        return params

    async def fake_fetch_json(ctx: FetcherContextType, client: Any, url: str, *, params: dict[str, Any] | None = None):
        assert params is not None
        pn = int(params["pn"])
        calls.append(pn)
        pages = {
            1: {
                "code": 0,
                "data": {
                    "page": {"count": 90},
                    "list": {
                        "vlist": [
                            {"bvid": "BVnew", "created": 250},
                            {"bvid": "BVhit1", "created": 150},
                        ]
                    },
                },
            },
            2: {
                "code": 0,
                "data": {
                    "page": {"count": 90},
                    "list": {
                        "vlist": [
                            {"bvid": "BVhit2", "created": 100},
                            {"bvid": "BVold", "created": 99},
                        ]
                    },
                },
            },
        }
        return Success(pages[pn])

    monkeypatch.setattr(space_module, "get_wbi_img", fake_get_wbi_img)
    monkeypatch.setattr(space_module, "encode_wbi", fake_encode_wbi)
    monkeypatch.setattr(space_module.Fetcher, "fetch_json", fake_fetch_json)

    all_avid = await get_user_space_all_videos_avids(
        FetcherContext(),
        cast("Any", object()),
        mid=MId("2147413451"),
        pubdate_filter=lambda timestamp: 100 <= timestamp < 200,
        stop_before_timestamp=100,
    )

    assert all_avid == [BvId("BVhit1"), BvId("BVhit2")]
    assert calls == [1, 2]


@pytest.mark.api
@as_sync
async def test_get_user_space_all_videos_avids_stops_on_api_error(monkeypatch: pytest.MonkeyPatch):
    errors: list[str] = []

    async def fake_get_wbi_img(ctx: FetcherContextType, client: Any) -> object:
        return object()

    async def fake_fetch_json(ctx: FetcherContextType, client: Any, url: str, *, params: dict[str, Any] | None = None):
        return Success({"code": -352, "message": "风控校验失败", "data": {"v_voucher": "voucher"}})

    monkeypatch.setattr(space_module, "get_wbi_img", fake_get_wbi_img)
    monkeypatch.setattr(space_module, "encode_wbi", lambda params, wbi_img: params)
    monkeypatch.setattr(space_module.Fetcher, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(space_module.Logger, "error", errors.append)

    all_avid = await get_user_space_all_videos_avids(FetcherContext(), cast("Any", object()), mid=MId("2147413451"))

    assert all_avid == []
    assert errors == ["获取用户空间视频列表第 1 页失败：风控校验失败（code: -352）"]


@pytest.mark.api
@as_sync
async def test_fetch_json_wraps_max_retry_error():
    class TimeoutClient:
        async def get(self, url: str, *, params: dict[str, str] | None = None) -> None:
            raise httpx.ReadTimeout("timeout")

    match await Fetcher.fetch_json(FetcherContext(), cast("Any", TimeoutClient()), "https://example.com"):
        case Failure(error):
            assert error.message == "超出最大重试次数！"
        case result:
            pytest.fail(f"expected Failure, got {result}")


@pytest.mark.api
@as_sync
async def test_get_user_name_returns_fallback_on_api_error(monkeypatch: pytest.MonkeyPatch):
    errors: list[str] = []

    async def fake_get_wbi_img(ctx: FetcherContextType, client: Any) -> object:
        return object()

    async def fake_touch_url(ctx: FetcherContextType, client: Any, url: str):
        return Success(None)

    async def fake_fetch_json(ctx: FetcherContextType, client: Any, url: str, *, params: dict[str, Any] | None = None):
        return Success({"code": -352, "message": "风控校验失败", "data": {"v_voucher": "voucher"}})

    monkeypatch.setattr(space_module, "get_wbi_img", fake_get_wbi_img)
    monkeypatch.setattr(space_module, "encode_wbi", lambda params, wbi_img: params)
    monkeypatch.setattr(space_module.Fetcher, "touch_url", fake_touch_url)
    monkeypatch.setattr(space_module.Fetcher, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(space_module.Logger, "error", errors.append)

    username = await get_user_name(FetcherContext(), cast("Any", object()), mid=MId("2147413451"))

    assert username == "「用户2147413451」"
    assert errors == [
        "获取用户名失败了呢，错误信息：风控校验失败，可尝试检查 `--auth` 参数正确性或者通过 `yutto auth login` 登录账号后重试～"
    ]


@pytest.mark.api
@pytest.mark.ignore
@as_sync
async def test_get_user_name():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        username = await get_user_name(ctx, client, mid=mid)
        assert username == "时雨千陌"


@pytest.mark.api
@as_sync
async def test_get_favourite_info():
    fid = FId("1306978874")
    ctx = FetcherContext()
    async with create_client() as client:
        fav_info = await get_favourite_info(ctx, client, fid=fid)
        assert fav_info["fid"] == fid
        assert fav_info["title"] == "Test"


@pytest.mark.api
@as_sync
async def test_get_favourite_avids():
    fid = FId("1306978874")
    ctx = FetcherContext()
    async with create_client() as client:
        avids = await get_favourite_avids(ctx, client, fid=fid)
        assert AId("456782499") in avids or BvId("BV1o541187Wh") in avids


@pytest.mark.api
@as_sync
async def test_all_favourites():
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        fav_list = await get_all_favourites(ctx, client, mid=mid)
        assert {"fid": FId("1306978874"), "title": "Test"} in fav_list


@pytest.mark.api
@as_sync
async def test_get_medialist_avids():
    series_id = SeriesId("1947439")
    mid = MId("100969474")
    ctx = FetcherContext()
    async with create_client() as client:
        avids = await get_medialist_avids(ctx, client, series_id=series_id, mid=mid)
        assert avids == [BvId("BV1Y441167U2"), BvId("BV1vZ4y1M7mQ")]


@pytest.mark.api
@as_sync
async def test_get_medialist_title():
    series_id = SeriesId("1947439")
    ctx = FetcherContext()
    async with create_client() as client:
        title = await get_medialist_title(ctx, client, series_id=series_id)
        assert title == "一个小视频列表～"
