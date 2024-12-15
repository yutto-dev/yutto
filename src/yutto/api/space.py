from __future__ import annotations

import math
from typing import TYPE_CHECKING

from yutto._typing import AvId, BvId, FavouriteMetaData, FId, MId, SeriesId
from yutto.api.user_info import encode_wbi, get_wbi_img
from yutto.exceptions import NotLoginError
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher, FetcherContext

if TYPE_CHECKING:
    from httpx import AsyncClient


# 个人空间·全部
async def get_user_space_all_videos_avids(ctx: FetcherContext, client: AsyncClient, mid: MId) -> list[AvId]:
    space_videos_api = "https://api.bilibili.com/x/space/wbi/arc/search"
    # ps 随机设置有时会出现错误，因此暂时固定在 30
    # ps: int = random.randint(3, 6) * 10
    ps = 30
    pn = 1
    total = 1
    all_avid: list[AvId] = []
    wbi_img = await get_wbi_img(ctx, client)
    while pn <= total:
        params = {
            "mid": mid,
            "ps": ps,
            "tid": 0,
            "pn": pn,
            "order": "pubdate",
        }
        params = encode_wbi(params, wbi_img)
        json_data = await Fetcher.fetch_json(ctx, client, space_videos_api, params=params)
        assert json_data is not None
        total = math.ceil(json_data["data"]["page"]["count"] / ps)
        pn += 1
        all_avid += [BvId(video_info["bvid"]) for video_info in json_data["data"]["list"]["vlist"]]
    return all_avid


# 个人空间·用户名
async def get_user_name(ctx: FetcherContext, client: AsyncClient, mid: MId) -> str:
    wbi_img = await get_wbi_img(ctx, client)
    params = {"mid": mid}
    params = encode_wbi(params, wbi_img)
    space_info_api = "https://api.bilibili.com/x/space/wbi/acc/info"
    await Fetcher.touch_url(ctx, client, "https://www.bilibili.com")
    user_info = await Fetcher.fetch_json(ctx, client, space_info_api, params=params)
    assert user_info is not None
    if user_info["code"] == -404:
        Logger.warning(f"用户 {mid} 不存在，疑似注销或被封禁")
        return f"「用户{mid}」"
    elif user_info["code"] != 0:
        Logger.error(f"获取用户名失败，错误信息：{user_info['message']}，可尝试添加参数 `-c` 登录账号后重试")
    return user_info["data"]["name"]


# 个人空间·收藏夹·信息
async def get_favourite_info(ctx: FetcherContext, client: AsyncClient, fid: FId) -> FavouriteMetaData:
    api = "https://api.bilibili.com/x/v3/fav/folder/info?media_id={fid}"
    json_data = await Fetcher.fetch_json(ctx, client, api.format(fid=fid))
    assert json_data is not None
    data = json_data["data"]
    return FavouriteMetaData(title=data["title"], fid=FId(str(data["id"])))


# 个人空间·收藏夹·avid
async def get_favourite_avids(ctx: FetcherContext, client: AsyncClient, fid: FId) -> list[AvId]:
    api = "https://api.bilibili.com/x/v3/fav/resource/ids?media_id={fid}"
    json_data = await Fetcher.fetch_json(ctx, client, api.format(fid=fid))
    assert json_data is not None
    return [BvId(video_info["bvid"]) for video_info in json_data["data"]]


# 个人空间·收藏夹·全部
async def get_all_favourites(ctx: FetcherContext, client: AsyncClient, mid: MId) -> list[FavouriteMetaData]:
    api = "https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={mid}"
    json_data = await Fetcher.fetch_json(ctx, client, api.format(mid=mid))
    assert json_data is not None
    if not json_data["data"]:
        return []
    return [FavouriteMetaData(title=data["title"], fid=FId(str(data["id"]))) for data in json_data["data"]["list"]]


# 个人空间·视频列表·avid
async def get_medialist_avids(ctx: FetcherContext, client: AsyncClient, series_id: SeriesId, mid: MId) -> list[AvId]:
    api = "https://api.bilibili.com/x/series/archives?mid={mid}&series_id={series_id}&only_normal=true&pn={pn}&ps={ps}"
    ps = 30
    pn = 1
    total = 1
    all_avid: list[AvId] = []

    while pn <= total:
        url = api.format(series_id=series_id, mid=mid, ps=ps, pn=pn)
        json_data = await Fetcher.fetch_json(ctx, client, url)
        assert json_data is not None
        total = math.ceil(json_data["data"]["page"]["total"] / ps)
        pn += 1
        all_avid += [BvId(video_info["bvid"]) for video_info in json_data["data"]["archives"]]
    return all_avid


# 个人空间·视频列表·标题
async def get_medialist_title(ctx: FetcherContext, client: AsyncClient, series_id: SeriesId) -> str:
    api = "https://api.bilibili.com/x/v1/medialist/info?type=5&biz_id={series_id}"
    json_data = await Fetcher.fetch_json(ctx, client, api.format(series_id=series_id))
    assert json_data is not None
    return json_data["data"]["title"]


# 个人空间·稍后再看
async def get_watch_later_avids(ctx: FetcherContext, client: AsyncClient) -> list[AvId]:
    api = "https://api.bilibili.com/x/v2/history/toview/web"
    json_data = await Fetcher.fetch_json(ctx, client, api)
    assert json_data is not None
    if json_data["code"] in [-101, -400]:
        raise NotLoginError("账号未登录，无法获取稍后再看列表哦~ Ծ‸Ծ")
    # TODO: 处理其他code不为0的异常
    return [BvId(video_info["bvid"]) for video_info in json_data["data"]["list"]]
