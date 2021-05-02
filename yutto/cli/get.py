import argparse
import aiohttp
from yutto.processor.crawler import gen_cookies, gen_headers
from yutto.utils.functiontools.sync import sync
import sys

from yutto.processor.downloader import download_video
from yutto.api.bangumi import get_bangumi_playurl, get_bangumi_title, get_season_id_by_episode_id, get_bangumi_list
from yutto.api.acg_video import get_acg_video_title, get_acg_video_playurl
from yutto.api.types import AvId, AId, BvId, EpisodeId, MediaId, SeasonId, CId
from yutto.processor.urlparser import regexp_bangumi_ep
from yutto.utils.console.logger import Logger
from yutto.utils.console.formatter import repair_filename


def add_get_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("url", help="视频主页 url")
    parser.set_defaults(action=run)


@sync
async def run(args: argparse.Namespace):
    async with aiohttp.ClientSession(
        headers=gen_headers(), cookies=gen_cookies(args.sessdata), timeout=aiohttp.ClientTimeout(total=5)
    ) as session:
        if match_obj := regexp_bangumi_ep.match(args.url):
            episode_id = EpisodeId(match_obj.group("episode_id"))
            season_id = await get_season_id_by_episode_id(session, episode_id)
            bangumi_list = await get_bangumi_list(session, season_id)
            for bangumi_item in bangumi_list:
                if bangumi_item["episode_id"] == episode_id:
                    avid = bangumi_item["avid"]
                    cid = bangumi_item["cid"]
                    filename = bangumi_item["name"]
                    break
            else:
                Logger.error("在列表中未找到该剧集")
                sys.exit(1)
            videos, audios = await get_bangumi_playurl(session, avid, episode_id, cid)
            # title = await get_bangumi_title(session, season_id)
        else:
            Logger.error("url 不正确～")
            sys.exit(1)
        await download_video(
            session,
            videos,
            audios,
            args.dir,
            repair_filename(filename),
            {
                "require_video": args.require_video,
                "video_quality": args.video_quality,
                "video_download_codec": args.vcodec.split(":")[0],
                "video_save_codec": args.vcodec.split(":")[1],
                "require_audio": args.require_audio,
                "audio_quality": args.audio_quality,
                "audio_download_codec": args.acodec.split(":")[0],
                "audio_save_codec": args.acodec.split(":")[1],
                "overwrite": args.overwrite,
                "block_size": int(args.block_size * 1024 * 1024),
                "num_workers": args.num_workers,
            },
        )
