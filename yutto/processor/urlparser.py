import re
import urllib
import urllib.request
from typing import Optional, TextIO

from yutto.utils.console.logger import Logger

# avid
regexp_acg_video_av = re.compile(r"https?://www\.bilibili\.com/video/av(?P<aid>\d+)(\?p=(?P<page>\d+))?")

# bvid
regexp_acg_video_bv = re.compile(r"https?://www\.bilibili\.com/video/(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")

# media id
regexp_bangumi_md = re.compile(r"https?://www\.bilibili\.com/bangumi/media/md(?P<media_id>\d+)")

# episode id
regexp_bangumi_ep = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")

# season id
regexp_bangumi_ss = re.compile(r"https?://www\.bilibili\.com/bangumi/play/ss(?P<season_id>\d+)")


def is_comment(line: str) -> bool:
    """ 判断文件某行是否为注释 """
    if line.startswith("#"):
        return True
    return False


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
