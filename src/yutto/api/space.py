from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from yutto.api.user_info import encode_wbi, get_wbi_img
from yutto.exceptions import NotLoginError
from yutto.types import BvId, FavouriteMetaData, FavouriteVideoData, FId
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import Fetcher

if TYPE_CHECKING:
    from httpx import AsyncClient

    from yutto.types import AvId, MId, SeriesId
    from yutto.utils.fetcher import FetcherContext


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
        Logger.error(
            f"获取用户名失败了呢，错误信息：{user_info['message']}，可尝试检查 `--auth` 参数正确性或者通过 `yutto auth login` 登录账号后重试～"
        )
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


# 个人空间·收藏夹·条目（含标题和分 p 数量）
async def get_favourite_items(ctx: FetcherContext, client: AsyncClient, fid: FId) -> list[FavouriteVideoData]:
    """获取收藏夹中所有视频的元数据，包含 B 站侧标题和分 p 数量。

    相比 get_favourite_avids，此接口通过分页列表 API 拉取完整标题，
    可用于区分单分 p / 多分 p 视频，以及使用人工标题替换机器生成的文件名。

    Args:
        ctx: 请求上下文，含 Cookie 和代理配置。
        client: httpx 异步客户端。
        fid: 收藏夹 ID。

    Returns:
        FavouriteVideoData 列表，每项含 avid、title（B 站标题）和 page（分 p 数）。
    """
    api = "https://api.bilibili.com/x/v3/fav/resource/list?media_id={fid}&pn={pn}&ps={ps}&platform=web"
    ps = 20
    pn = 1
    favourite_items: list[FavouriteVideoData] = []

    while True:
        json_data = await Fetcher.fetch_json(ctx, client, api.format(fid=fid, pn=pn, ps=ps))
        assert json_data is not None
        data = cast("dict[str, Any]", json_data["data"])
        medias = cast("list[dict[str, Any]]", data["medias"] or [])
        # 仅保留正常视频（type=2），过滤已失效条目（bvid 为空）
        favourite_items.extend(
            FavouriteVideoData(
                avid=BvId(media["bvid"]),
                title=str(media["title"]),
                page=int(media["page"]),
            )
            for media in medias
            if media.get("type") == 2 and media.get("bvid")
        )

        # 优先使用 has_more 字段判断翻页；接口不返回时退回到条目数判断
        has_more = data.get("has_more")
        if has_more is not None:
            if not has_more:
                break
        elif len(medias) < ps:
            break

        pn += 1

    return favourite_items


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
