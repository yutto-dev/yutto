import math

from aiohttp import ClientSession

from yutto._typing import AvId, BvId, FavouriteMetaData, FId, MId, SeriesId
from yutto.utils.fetcher import Fetcher


# 个人空间·全部
async def get_uploader_space_all_videos_avids(session: ClientSession, mid: MId) -> list[AvId]:
    space_videos_api = (
        "https://api.bilibili.com/x/space/arc/search?mid={mid}&ps={ps}&tid=0&pn={pn}&order=pubdate&jsonp=jsonp"
    )
    # ps 随机设置有时会出现错误，因此暂时固定在 30
    # ps: int = random.randint(3, 6) * 10
    ps = 30
    pn = 1
    total = 1
    all_avid: list[AvId] = []
    while pn <= total:
        space_videos_url = space_videos_api.format(mid=mid, ps=ps, pn=pn)
        json_data = await Fetcher.fetch_json(session, space_videos_url)
        assert json_data is not None
        total = math.ceil(json_data["data"]["page"]["count"] / ps)
        pn += 1
        all_avid += [BvId(video_info["bvid"]) for video_info in json_data["data"]["list"]["vlist"]]
    return all_avid


# 个人空间·用户名
async def get_uploader_name(session: ClientSession, mid: MId) -> str:
    space_info_api = "https://api.bilibili.com/x/space/acc/info?mid={mid}&jsonp=jsonp"
    space_info_url = space_info_api.format(mid=mid)
    uploader_info = await Fetcher.fetch_json(session, space_info_url)
    assert uploader_info is not None
    return uploader_info["data"]["name"]


# 个人空间·收藏夹·信息
async def get_favourite_info(session: ClientSession, fid: FId) -> FavouriteMetaData:
    api = "https://api.bilibili.com/x/v3/fav/folder/info?media_id={fid}"
    json_data = await Fetcher.fetch_json(session, api.format(fid=fid))
    assert json_data is not None
    data = json_data["data"]
    return FavouriteMetaData(title=data["title"], fid=FId(str(data["id"])))


# 个人空间·收藏夹·avid
async def get_favourite_avids(session: ClientSession, fid: FId) -> list[AvId]:
    api = "https://api.bilibili.com/x/v3/fav/resource/ids?media_id={fid}"
    json_data = await Fetcher.fetch_json(session, api.format(fid=fid))
    assert json_data is not None
    return [BvId(video_info["bvid"]) for video_info in json_data["data"]]


# 个人空间·收藏夹·全部
async def get_all_favourites(session: ClientSession, mid: MId) -> list[FavouriteMetaData]:
    api = "https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={mid}"
    json_data = await Fetcher.fetch_json(session, api.format(mid=mid))
    assert json_data is not None
    if not json_data["data"]:
        return []
    return [FavouriteMetaData(title=data["title"], fid=FId(str(data["id"]))) for data in json_data["data"]["list"]]


# 个人空间·视频列表·avid
async def get_medialist_avids(session: ClientSession, series_id: SeriesId) -> list[AvId]:
    api = "https://api.bilibili.com/x/v2/medialist/resource/list?type=5&otype=2&biz_id={series_id}"
    json_data = await Fetcher.fetch_json(session, api.format(series_id=series_id))
    assert json_data is not None
    if not json_data["data"]:
        return []
    return [BvId(video_info["bv_id"]) for video_info in json_data["data"]["media_list"]]


# 个人空间·视频列表·标题
async def get_medialist_title(session: ClientSession, series_id: SeriesId) -> str:
    api = "https://api.bilibili.com/x/v1/medialist/info?type=5&biz_id={series_id}"
    json_data = await Fetcher.fetch_json(session, api.format(series_id=series_id))
    assert json_data is not None
    return json_data["data"]["title"]


# 个人空间·视频合集·avid
async def get_collection_avids(session: ClientSession, series_id: SeriesId) -> list[AvId]:
    api = "https://api.bilibili.com/x/polymer/space/seasons_archives_list?mid=477782158&season_id={series_id}&sort_reverse=false&page_num={pn}&page_size={ps}"
    ps = 30
    pn = 1
    total = 1
    all_avid: list[AvId] = []
    while pn <= total:
        space_videos_url = api.format(series_id=series_id, ps=ps, pn=pn)
        json_data = await Fetcher.fetch_json(session, space_videos_url)
        assert json_data is not None
        total = math.ceil(json_data["data"]["page"]["total"] / ps)
        pn += 1
        all_avid += [BvId(archives["bvid"]) for archives in json_data["data"]["archives"]]
    return all_avid


# 个人空间·视频合集·标题
async def get_collection_title(session: ClientSession, series_id: SeriesId) -> str:
    api = "https://api.bilibili.com/x/v1/medialist/info?type=8&biz_id={series_id}"
    json_data = await Fetcher.fetch_json(session, api.format(series_id=series_id))
    assert json_data is not None
    return json_data["data"]["title"]
