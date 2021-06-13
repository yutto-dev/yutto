import re
from typing import Optional

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


def alias_parser(alias_text: Optional[str]) -> dict[str, str]:
    if alias_text is None:
        return {}
    result: dict[str, str] = {}
    re_alias_spliter = re.compile(r"[\s=]")
    for line in alias_text:
        line = line.rstrip()
        alias, url = re_alias_spliter.split(line, maxsplit=1)
        result[alias] = url
    return result
