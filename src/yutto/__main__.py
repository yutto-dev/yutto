from __future__ import annotations

import argparse
import asyncio
import copy
import os
import re
import sys
from typing import TYPE_CHECKING, Any, Callable, Literal

import httpx
from typing_extensions import TypeAlias

from yutto.__version__ import VERSION as yutto_version
from yutto.bilibili_typing.quality import (
    audio_quality_priority_default,
    video_quality_priority_default,
)
from yutto.exceptions import ErrorCode
from yutto.extractor import (
    BangumiBatchExtractor,
    BangumiExtractor,
    CheeseBatchExtractor,
    CheeseExtractor,
    CollectionExtractor,
    FavouritesExtractor,
    SeriesExtractor,
    UgcVideoBatchExtractor,
    UgcVideoExtractor,
    UserAllFavouritesExtractor,
    UserAllUgcVideosExtractor,
    UserWatchLaterExtractor,
)
from yutto.processor.downloader import DownloadState, start_downloader
from yutto.processor.parser import alias_parser, file_scheme_parser
from yutto.processor.path_resolver import create_unique_path_resolver
from yutto.utils.asynclib import sleep_with_status_bar_refresh
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import Fetcher, create_client
from yutto.utils.funcutils import as_sync
from yutto.utils.time import TIME_DATE_FMT, TIME_FULL_FMT
from yutto.validator import (
    initial_validation,
    validate_basic_arguments,
    validate_batch_arguments,
    validate_user_info,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from yutto._typing import EpisodeData

DownloadResourceType: TypeAlias = Literal["video", "audio", "subtitle", "metadata", "danmaku", "cover", "chapter_info"]
DOWNLOAD_RESOURCE_TYPES: list[DownloadResourceType] = [
    "video",
    "audio",
    "subtitle",
    "metadata",
    "danmaku",
    "cover",
    "chapter_info",
]


def main():
    parser = cli()
    args = parser.parse_args()
    initial_validation(args)
    args_list = flatten_args(args, parser)
    try:
        run(args_list)
    except (SystemExit, KeyboardInterrupt, asyncio.exceptions.CancelledError):
        Logger.info("已终止下载，再次运行即可继续下载～")
        sys.exit(ErrorCode.PAUSED_DOWNLOAD.value)


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="yutto 一个可爱且任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {yutto_version}")
    # 如果需要创建其他子命令可参考
    # https://stackoverflow.com/questions/29998417/create-parser-with-subcommands-in-argparse-customize-positional-arguments
    parser.add_argument("url", help="视频主页 url 或 url 列表（需使用 file scheme）")
    group_common = parser.add_argument_group("common", "通用参数")
    group_common.add_argument("-n", "--num-workers", type=int, default=8, help="同时用于下载的最大 Worker 数")
    group_common.add_argument(
        "-q",
        "--video-quality",
        default=127,
        choices=video_quality_priority_default,
        type=int,
        help="视频清晰度等级（127:8K, 126:Dolby Vision, 125:HDR, 120:4K, 116:1080P60, 112:1080P+, 100:智能修复, 80:1080P, 74:720P60, 64:720P, 32:480P, 16:360P）",
    )
    group_common.add_argument(
        "-aq",
        "--audio-quality",
        default=30251,
        choices=audio_quality_priority_default,
        type=int,
        help="音频码率等级（30251:Hi-Res, 30255:Dolby Audio, 30250:Dolby Atmos, 30280:320kbps, 30232:128kbps, 30216:64kbps）",
    )
    group_common.add_argument(
        "--vcodec",
        default="avc:copy",
        metavar="DOWNLOAD_VCODEC:SAVE_VCODEC",
        help="视频编码格式（<下载格式>:<生成格式>）",
    )
    group_common.add_argument(
        "--acodec",
        default="mp4a:copy",
        metavar="DOWNLOAD_ACODEC:SAVE_ACODEC",
        help="音频编码格式（<下载格式>:<生成格式>）",
    )
    group_common.add_argument(
        "--download-vcodec-priority",
        default="auto",
        help="视频编码格式优先级，使用 `,` 分隔，如 `hevc,avc,av1`，默认为 `auto`，即根据 vcodec 中「下载编码」自动推断",
    )
    group_common.add_argument(
        "--output-format", default="infer", choices=["infer", "mp4", "mkv", "mov"], help="输出格式（infer 为自动推断）"
    )
    group_common.add_argument(
        "--output-format-audio-only",
        default="infer",
        choices=["infer", "aac", "mp3", "flac", "mp4", "mkv", "mov"],
        help="仅包含音频流时所使用的输出格式（infer 为自动推断）",
    )
    group_common.add_argument(
        "-df", "--danmaku-format", default="ass", choices=["xml", "ass", "protobuf"], help="弹幕类型"
    )
    group_common.add_argument(
        "-bs", "--block-size", default=0.5, type=float, help="分块下载时各块大小，单位为 MiB，默认为 0.5MiB"
    )
    group_common.add_argument("-w", "--overwrite", action="store_true", help="强制覆盖已下载内容")
    group_common.add_argument(
        "-x", "--proxy", default="auto", help="设置代理（auto 为系统代理、no 为不使用代理、当然也可以设置代理值）"
    )
    group_common.add_argument("-d", "--dir", default="./", help="下载目录，默认为运行目录")
    group_common.add_argument("--tmp-dir", help="用来存放下载过程中临时文件的目录，默认为下载目录")
    group_common.add_argument("-c", "--sessdata", default="", help="Cookies 中的 SESSDATA 字段")
    group_common.add_argument("-tp", "--subpath-template", default="{auto}", help="多级目录的存储路径模板")
    group_common.add_argument(
        "-af", "--alias-file", type=argparse.FileType("r", encoding="utf-8"), help="设置 url 别名文件路径"
    )
    group_common.add_argument(
        "--metadata-format-premiered", default=TIME_DATE_FMT, help="专用于 metadata 文件中 premiered 字段的日期格式"
    )
    group_common.add_argument("--download-interval", default=0, type=int, help="设置下载间隔，单位为秒")
    group_common.add_argument("--banned-mirrors-pattern", default=None, help="禁用下载链接的镜像源，使用正则匹配")

    # 资源选择
    group_common.add_argument(
        "--video-only",
        dest="require_audio",
        action=create_select_required_action(deselect=["audio"]),
        help="仅下载视频流",
    )
    group_common.add_argument(
        "--audio-only",
        dest="require_video",
        action=create_select_required_action(deselect=["video"]),
        help="仅下载音频流",
    )  # 视频和音频是反选对方，而不是其余反选所有的
    group_common.add_argument(
        "--no-danmaku",
        dest="require_danmaku",
        action=create_select_required_action(deselect=["danmaku"]),
        help="不生成弹幕文件",
    )
    group_common.add_argument(
        "--danmaku-only",
        dest="require_danmaku",
        action=create_select_required_action(select=["danmaku"], deselect=invert_selection(["danmaku"])),
        help="仅生成弹幕文件",
    )
    group_common.add_argument(
        "--no-subtitle",
        dest="require_subtitle",
        action=create_select_required_action(deselect=["subtitle"]),
        help="不生成字幕文件",
    )
    group_common.add_argument(
        "--subtitle-only",
        dest="require_subtitle",
        action=create_select_required_action(select=["subtitle"], deselect=invert_selection(["subtitle"])),
        help="仅生成字幕文件",
    )
    group_common.add_argument(
        "--with-metadata",
        dest="require_metadata",
        action=create_select_required_action(select=["metadata"]),
        help="生成元数据文件",
    )
    group_common.add_argument(
        "--metadata-only",
        dest="require_metadata",
        action=create_select_required_action(select=["metadata"], deselect=invert_selection(["metadata"])),
        help="仅生成元数据文件",
    )
    group_common.add_argument(
        "--no-cover",
        dest="require_cover",
        action=create_select_required_action(deselect=["cover"]),
        help="不生成封面",
    )

    group_common.add_argument(
        "--no-chapter-info",
        dest="require_chapter_info",
        action=create_select_required_action(deselect=["chapter_info"]),
        help="不封装章节信息",
    )

    group_common.set_defaults(
        require_video=True,
        require_audio=True,
        require_subtitle=True,
        require_metadata=False,
        require_danmaku=True,
        require_cover=True,
        require_chapter_info=True,
    )
    group_common.add_argument("--no-color", action="store_true", help="不使用颜色")
    group_common.add_argument("--no-progress", action="store_true", help="不显示进度条")
    group_common.add_argument("--debug", action="store_true", help="启用 debug 模式")
    group_common.add_argument("--vip-strict", action="store_true", help="启用严格检查大会员生效")
    group_common.add_argument("--login-strict", action="store_true", help="启用严格检查登录状态")

    # 仅批量下载使用
    group_batch = parser.add_argument_group("batch", "批量下载参数")
    group_batch.add_argument("-b", "--batch", action="store_true", help="批量下载")
    group_batch.add_argument("-p", "--episodes", default="1~-1", help="选集")
    group_batch.add_argument(
        "-s", "--with-section", action="store_true", help="同时下载附加剧集（PV、预告以及特别篇等专区内容）"
    )
    group_batch.add_argument("--batch-filter-start-time", help="只下载该时间之后（包含临界值）发布的稿件")
    group_batch.add_argument("--batch-filter-end-time", help="只下载该时间之前（不包含临界值）发布的稿件")

    # 仅任务列表中使用
    group_batch_file = parser.add_argument_group("batch file", "批量下载文件参数")
    group_batch_file.add_argument("--no-inherit", action="store_true", help="不继承父级参数")

    return parser


@as_sync
async def run(args_list: list[argparse.Namespace]):
    unique_path = create_unique_path_resolver()
    async with create_client(
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        proxy=Fetcher.proxy,
    ) as client:
        if len(args_list) > 1:
            Logger.info(f"列表里共检测到 {len(args_list)} 项")

        for i, args in enumerate(args_list):
            if len(args_list) > 1:
                Logger.custom(f"列表项 {args.url}", Badge(f"[{i+1}/{len(args_list)}]", fore="black", back="cyan"))

            # 验证批量参数
            if args.batch:
                validate_batch_arguments(args)

            # 初始化各种提取器
            extractors = (
                [
                    UgcVideoBatchExtractor(),  # 投稿全集
                    BangumiBatchExtractor(),  # 番剧全集
                    CheeseBatchExtractor(),  # 课程全集
                    FavouritesExtractor(),  # 用户单一收藏
                    UserAllFavouritesExtractor(),  # 用户全部收藏
                    SeriesExtractor(),  # 视频列表
                    CollectionExtractor(),  # 视频合集
                    UserAllUgcVideosExtractor(),  # 个人空间，由于个人空间的正则包含了收藏夹，所以需要放在收藏夹之后
                    UserWatchLaterExtractor(),  # 用户稍后再看
                ]
                if args.batch
                else [
                    UgcVideoExtractor(),  # 投稿单集
                    BangumiExtractor(),  # 番剧单话
                    CheeseExtractor(),  # 课程单集
                ]
            )
            url: str = args.url
            # 将 shortcut 转为完整 url
            for extractor in extractors:
                matched, url = extractor.resolve_shortcut(url)
                if matched:
                    break

            # 在开始前校验，减少对第一个视频的请求
            if not await validate_user_info({"is_login": args.login_strict, "vip_status": args.vip_strict}):
                Logger.error("启用了严格校验大会员或登录模式，请检查 SESSDATA 或大会员状态！")
                sys.exit(ErrorCode.NOT_LOGIN_ERROR.value)
            # 重定向到可识别的 url
            try:
                url = await Fetcher.get_redirected_url(client, url)
            except httpx.InvalidURL:
                Logger.error(f"无效的 url({url})～请检查一下链接是否正确～")
                sys.exit(ErrorCode.WRONG_URL_ERROR.value)
            except httpx.UnsupportedProtocol:
                error_text = f"无效的 url 协议（{url}）～请检查一下链接协议是否正确"
                if not args.batch:
                    error_text += (
                        "，如使用裸 id 功能，请确认该类型 id 是否支持当前单话模式，如不支持需要添加 `-b` 以使用批量模式"
                    )
                Logger.error(error_text)
                sys.exit(ErrorCode.WRONG_URL_ERROR.value)

            # 提取信息，构造解析任务～
            for extractor in extractors:
                if extractor.match(url):
                    download_list = await extractor(client, args)
                    break
            else:
                if args.batch:
                    # TODO: 指向文档中受支持的列表部分
                    Logger.error("url 不正确呦～")
                else:
                    Logger.error("url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～")
                sys.exit(ErrorCode.WRONG_URL_ERROR.value)

            current_download_state = DownloadState.SKIP

            # 下载～
            for i, episode_data_coro in enumerate(download_list):
                if episode_data_coro is None:
                    continue

                # 中途校验，因为批量下载时可能会失效
                if not await validate_user_info({"is_login": args.login_strict, "vip_status": args.vip_strict}):
                    Logger.error("启用了严格校验大会员或登录模式，请检查 SESSDATA 或大会员状态！")
                    sys.exit(ErrorCode.NOT_LOGIN_ERROR.value)

                if current_download_state != DownloadState.SKIP and args.download_interval > 0:
                    Logger.info(f"下载间隔 {args.download_interval} 秒")
                    await sleep_with_status_bar_refresh(args.download_interval)

                # 这时候才真正开始解析链接
                episode_data = await episode_data_coro
                if episode_data is None:
                    continue
                # 保证路径唯一
                episode_data = ensure_unique_path(episode_data, unique_path)
                if args.batch:
                    Logger.custom(
                        f"{episode_data['filename']}",
                        Badge(f"[{i+1}/{len(download_list)}]", fore="black", back="cyan"),
                    )

                current_download_state = await start_downloader(
                    client,
                    episode_data,
                    {
                        "require_video": args.require_video,
                        "require_chapter_info": args.require_chapter_info,
                        "video_quality": args.video_quality,
                        "video_download_codec": args.vcodec.split(":")[0],
                        "video_save_codec": args.vcodec.split(":")[1],
                        "video_download_codec_priority": (
                            args.download_vcodec_priority.split(",")
                            if args.download_vcodec_priority != "auto"
                            else None
                        ),
                        "require_audio": args.require_audio,
                        "audio_quality": args.audio_quality,
                        "audio_download_codec": args.acodec.split(":")[0],
                        "audio_save_codec": args.acodec.split(":")[1],
                        "output_format": args.output_format,
                        "output_format_audio_only": args.output_format_audio_only,
                        "overwrite": args.overwrite,
                        "block_size": int(args.block_size * 1024 * 1024),
                        "num_workers": args.num_workers,
                        "metadata_format": {
                            "premiered": args.metadata_format_premiered,
                            "dateadded": TIME_FULL_FMT,
                        },
                        "banned_mirrors_pattern": args.banned_mirrors_pattern,
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
    if re.match(r"file://", args.url) or os.path.isfile(args.url):  # noqa: PTH113
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


def create_select_required_action(
    select: list[DownloadResourceType] | None = None, deselect: list[DownloadResourceType] | None = None
):
    selected_items = select or []
    deselected_items = deselect or []

    class SelectRequiredAction(argparse.Action):
        def __init__(self, option_strings: str, dest: str, nargs: int | str | None = None, **kwargs: Any):
            if nargs is not None:
                raise ValueError("nargs not allowed")
            super().__init__(option_strings, dest, nargs=0, **kwargs)

        def __call__(
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: str | Sequence[str] | None,
            option_string: str | None = None,
        ):
            for select_item in selected_items:
                setattr(namespace, f"require_{select_item}", True)
            for deselect_item in deselected_items:
                setattr(namespace, f"require_{deselect_item}", False)

    return SelectRequiredAction


def invert_selection(select: list[DownloadResourceType]) -> list[DownloadResourceType]:
    return [tp for tp in DOWNLOAD_RESOURCE_TYPES if tp not in select]


def ensure_unique_path(episode_data: EpisodeData, unique_name_resolver: Callable[[str], str]) -> EpisodeData:
    original_filename = episode_data["filename"]
    new_name = unique_name_resolver(original_filename)
    episode_data["filename"] = new_name
    if original_filename != new_name:
        Logger.warning(f"文件名重复，已重命名为 {new_name}")
    return episode_data


if __name__ == "__main__":
    main()
