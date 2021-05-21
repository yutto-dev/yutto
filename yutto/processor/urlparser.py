import re

# avid
regexp_acg_video_av = re.compile(r"https?://(www\.|m\.)?bilibili\.com/video/av(?P<aid>\d+)(\?p=(?P<page>\d+))?")

# bvid
regexp_acg_video_bv = re.compile(r"https?://(www\.|m\.)?bilibili\.com/video/(?P<bvid>(bv|BV)\w+)(\?p=(?P<page>\d+))?")

# media id
regexp_bangumi_md = re.compile(r"https?://(www\.|m\.)?bilibili\.com/bangumi/media/md(?P<media_id>\d+)")

# episode id
regexp_bangumi_ep = re.compile(r"https?://(www\.|m\.)?bilibili\.com/bangumi/play/ep(?P<episode_id>\d+)")

# season id
regexp_bangumi_ss = re.compile(r"https?://(www\.|m\.)?bilibili\.com/bangumi/play/ss(?P<season_id>\d+)")
