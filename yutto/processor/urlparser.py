import re
import urllib
import urllib.request
from typing import Optional, TextIO

from yutto.utils.console.logger import Logger


regexp_acg_video_av = re.compile(r"https?://www\.bilibili\.com/video/av(?P<aid>\d+)(\?p=(?P<page>\d+))?")
regexp_acg_video_bv = re.compile(r"https?://www\.bilibili\.com/video/(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")
regexp_bangumi_md = re.compile(r"https?://www\.bilibili\.com/bangumi/media/md(?P<media_id>\d+)")
regexp_bangumi_ep = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")
regexp_bangumi_ss = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ss(?P<season_id>\d+)")
regexp_space_all = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)(/video)?")
regexp_favourite_all = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist")
regexp_favourite = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/favlist\?fid=(?P<fid>\d+)")
regexp_medialist = re.compile(
    r"https?://www\.bilibili\.com/medialist/play/(?P<mid>\d+)\?business=space_series&business_id=(?P<series_id>\d+)"
)
regexp_series = re.compile(r"https?://space\.bilibili\.com/(?P<mid>\d+)/channel/seriesdetail\?sid=(?P<series_id>\d+)")

regexp_acg_video_av_bare = re.compile(r"av(?P<aid>\d+)(\?p=(?P<page>\d+))?")
regexp_acg_video_bv_bare = re.compile(r"(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")
regexp_bangumi_md_bare = re.compile(r"md(?P<media_id>\d+)")
regexp_bangumi_ep_bare = re.compile(r"ep(?P<episode_id>\d+)")
regexp_bangumi_ss_bare = re.compile(r"ss(?P<season_id>\d+)")


def is_comment(line: str) -> bool:
    """判断文件某行是否为注释"""
    if line.startswith("#"):
        return True
    return False


def bare_name_parser(bare_name: str) -> str:
    url: str = bare_name
    if match_obj := regexp_acg_video_av_bare.match(bare_name):
        page: int = 1
        if match_obj.group("page") is not None:
            page = int(match_obj.group("page"))
        url = f"https://www.bilibili.com/video/av{match_obj.group('aid')}?p={page}"
    elif match_obj := regexp_acg_video_bv_bare.match(bare_name):
        page: int = 1
        if match_obj.group("page") is not None:
            page = int(match_obj.group("page"))
        url = f"https://www.bilibili.com/video/{match_obj.group('bvid')}?p={page}"
    elif match_obj := regexp_bangumi_md_bare.match(bare_name):
        url = f"https://www.bilibili.com/bangumi/media/md{match_obj.group('media_id')}"
    elif match_obj := regexp_bangumi_ep_bare.match(bare_name):
        url = f"https://www.bilibili.com/bangumi/play/ep{match_obj.group('episode_id')}"
    elif match_obj := regexp_bangumi_ss_bare.match(bare_name):
        url = f"https://www.bilibili.com/bangumi/play/ss{match_obj.group('season_id')}"
    return url


def alias_parser(f_alias: Optional[TextIO]) -> dict[str, str]:
    if f_alias is None:
        return {}
    f_alias.seek(0)
    result: dict[str, str] = {}
    re_alias_spliter = re.compile(r"[\s=]")
    for line in f_alias:
        line = line.strip()
        if not line or is_comment(line):
            continue
        alias, url = re_alias_spliter.split(line, maxsplit=1)
        result[alias] = url
    return result


def file_scheme_parser(url: str) -> list[str]:
    file_url: str = urllib.parse.urlparse(url).path
    file_path: str = urllib.request.url2pathname(file_url)
    Logger.info("解析下载列表 {} 中...".format(file_path))
    result: list[str] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or is_comment(line):
                continue
            result.append(line)
    return result
