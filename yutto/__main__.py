import argparse
import copy
import os
import re
import sys

import aiohttp

from yutto.validator import initial_validate, validate_basic_arguments, validate_batch_argments
from yutto.__version__ import VERSION as yutto_version
from yutto.bilibili_typing.quality import audio_quality_priority_default, video_quality_priority_default
from yutto.exceptions import ErrorCode
from yutto.extractor import (
    AcgVideoBatchExtractor,
    AcgVideoExtractor,
    BangumiBatchExtractor,
    BangumiExtractor,
    FavouritesAllExtractor,
    FavouritesExtractor,
    SeriesExtractor,
    UploaderAllVideosExtractor,
)
from yutto.processor.downloader import start_downloader
from yutto.processor.parser import alias_parser, file_scheme_parser
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher
from yutto.utils.functools import as_sync


def main():
    parser = cli()
    args = parser.parse_args()
    initial_validate(args)
    args_list = flatten_args(args, parser)
    try:
        run(args_list)
    except (SystemExit, KeyboardInterrupt):
        Logger.info("已终止下载，再次运行即可继续下载～")
        sys.exit(ErrorCode.PAUSED_DOWNLOAD.value)


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="yutto 一个可爱且任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {yutto_version}")
    parser.add_argument("url", help="视频主页 url 或 url 列表（需使用 file scheme）")
    group_common = parser.add_argument_group("common", "通用参数")
    group_common.add_argument("-n", "--num-workers", type=int, default=8, help="同时用于下载的最大 Worker 数")
    group_common.add_argument(
        "-q",
        "--video-quality",
        default=127,
        choices=video_quality_priority_default,
        type=int,
        help="视频清晰度等级（127:8K, 126: Dolby Vision, 125:HDR, 120:4K, 116:1080P60, 112:1080P+, 80:1080P, 74:720P60, 64:720P, 32:480P, 16:360P）",
    )
    group_common.add_argument(
        "-aq",
        "--audio-quality",
        default=30280,
        choices=audio_quality_priority_default,
        type=int,
        help="音频码率等级（30280:320kbps, 30232:128kbps, 30216:64kbps）",
    )
    group_common.add_argument(
        "--vcodec", default="avc:copy", metavar="DOWNLOAD_VCODEC:SAVE_VCODEC", help="视频编码格式（<下载格式>:<生成格式>）"
    )
    group_common.add_argument(
        "--acodec", default="mp4a:copy", metavar="DOWNLOAD_ACODEC:SAVE_ACODEC", help="音频编码格式（<下载格式>:<生成格式>）"
    )
    group_common.add_argument("--video-only", dest="require_audio", action="store_false", help="只下载视频")
    group_common.add_argument("--audio-only", dest="require_video", action="store_false", help="只下载音频")
    group_common.add_argument("-df", "--danmaku-format", default="ass", choices=["xml", "ass", "protobuf"], help="弹幕类型")
    group_common.add_argument("-bs", "--block-size", default=0.5, type=float, help="分块下载时各块大小，单位为 MiB，默认为 0.5MiB")
    group_common.add_argument("-w", "--overwrite", action="store_true", help="强制覆盖已下载内容")
    group_common.add_argument("-x", "--proxy", default="auto", help="设置代理（auto 为系统代理、no 为不使用代理、当然也可以设置代理值）")
    group_common.add_argument("-d", "--dir", default="./", help="下载目录，默认为运行目录")
    group_common.add_argument("--tmp-dir", help="用来存放下载过程中临时文件的目录，默认为下载目录")
    group_common.add_argument("-c", "--sessdata", default="", help="Cookies 中的 SESSDATA 字段")
    group_common.add_argument("-tp", "--subpath-template", default="{auto}", help="多级目录的存储路径模板")
    group_common.add_argument(
        "-af", "--alias-file", type=argparse.FileType("r", encoding="utf-8"), help="设置 url 别名文件路径"
    )
    group_common.add_argument("--no-danmaku", action="store_true", help="不生成弹幕文件")
    group_common.add_argument("--no-subtitle", action="store_true", help="不生成字幕文件")
    group_common.add_argument("--with-metadata", action="store_true", help="生成元数据文件")
    group_common.add_argument("--metadata-format", default="nfo", choices=["nfo"], help="（待实现）元数据文件类型，目前仅支持 nfo")
    group_common.add_argument("--embed-danmaku", action="store_true", help="（待实现）将弹幕文件嵌入到视频中")
    group_common.add_argument("--embed-subtitle", default=None, help="（待实现）将字幕文件嵌入到视频中（需输入语言代码）")
    group_common.add_argument("--no-color", action="store_true", help="不使用颜色")
    group_common.add_argument("--no-progress", action="store_true", help="不显示进度条")
    group_common.add_argument("--debug", action="store_true", help="启用 debug 模式")

    # 仅批量下载使用
    group_batch = parser.add_argument_group("batch", "批量下载参数")
    group_batch.add_argument("-b", "--batch", action="store_true", help="批量下载")
    group_batch.add_argument("-p", "--episodes", default="1~-1", help="选集")
    group_batch.add_argument("-s", "--with-section", action="store_true", help="同时下载附加剧集（PV、预告以及特别篇等专区内容）")

    # 仅任务列表中使用
    group_batch_file = parser.add_argument_group("batch file", "批量下载文件参数")
    group_batch_file.add_argument("--no-inherit", action="store_true", help="不继承父级参数")

    return parser


@as_sync
async def run(args_list: list[argparse.Namespace]):
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        if len(args_list) > 1:
            Logger.info(f"列表里共检测到 {len(args_list)} 项")

        for i, args in enumerate(args_list):
            if len(args_list) > 1:
                Logger.custom(f"列表项 {args.url}", Badge(f"[{i+1}/{len(args_list)}]", fore="black", back="cyan"))

            # 验证批量参数
            if args.batch:
                validate_batch_argments(args)

            # 初始化各种提取器
            extractors = (
                [
                    AcgVideoBatchExtractor(),  # 投稿全集
                    BangumiBatchExtractor(),  # 番剧全集
                    FavouritesExtractor(),  # 用户单一收藏
                    FavouritesAllExtractor(),  # 用户全部收藏
                    SeriesExtractor(),  # 视频合集、视频列表
                    UploaderAllVideosExtractor(),  # 个人空间，由于个人空间的正则包含了收藏夹，所以需要放在收藏夹之后
                ]
                if args.batch
                else [
                    AcgVideoExtractor(),  # 投稿单集
                    BangumiExtractor(),  # 番剧单话
                ]
            )

            url: str = args.url
            # 将 shortcut 转为完整 url
            for extractor in extractors:
                matched, url = extractor.resolve_shortcut(url)
                if matched:
                    break

            # 重定向到可识别的 url
            try:
                url = await Fetcher.get_redirected_url(session, url)
            except aiohttp.client_exceptions.InvalidURL:  # type: ignore
                Logger.error("无效的 url～请检查一下链接是否正确～")
                sys.exit(ErrorCode.WRONG_URL_ERROR.value)

            # 提取信息，构造解析任务～
            for extractor in extractors:
                if extractor.match(url):
                    download_list = await extractor(session, args)
                    break
            else:
                if args.batch:
                    # TODO: 指向文档中受支持的列表部分
                    Logger.error("url 不正确呦～")
                else:
                    Logger.error("url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～")
                sys.exit(ErrorCode.WRONG_URL_ERROR.value)

            # 下载～
            for i, episode_data_coro in enumerate(download_list):
                if episode_data_coro is None:
                    continue
                # 这时候才真正开始解析链接
                episode_data = await episode_data_coro
                if episode_data is None:
                    continue
                if args.batch:
                    Logger.custom(
                        f"{episode_data['filename']}",
                        Badge(f"[{i+1}/{len(download_list)}]", fore="black", back="cyan"),
                    )
                await start_downloader(
                    session,
                    episode_data,
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
                Logger.new_line()
            Logger.new_line()


def flatten_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[argparse.Namespace]:
    """递归展平列表参数"""
    args = copy.copy(args)
    validate_basic_arguments(args)
    # 查看是否存在于 alias 中
    alias_map = alias_parser(args.alias_file)
    if args.url in alias_map:
        args.url = alias_map[args.url]

    # 是否为下载列表
    if re.match(r"file://", args.url) or os.path.isfile(args.url):
        args_list: list[argparse.Namespace] = []
        # TODO: 如果是相对路径，需要相对于当前 list 路径
        for line in file_scheme_parser(args.url):
            local_args = parser.parse_args(line.split(), args)
            if local_args.no_inherit:
                local_args = parser.parse_args(line.split())
            Logger.debug(f"列表参数: {local_args}")
            args_list += flatten_args(local_args, parser)
        return args_list
    else:
        return [args]


if __name__ == "__main__":
    main()
