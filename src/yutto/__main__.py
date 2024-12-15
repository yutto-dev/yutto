from __future__ import annotations

import asyncio
import copy
import os
import re
import sys
from typing import TYPE_CHECKING, Callable

import httpx
from biliass import BlockOptions

from yutto.cli.cli import cli
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
from yutto.processor.parser import file_scheme_parser
from yutto.processor.path_resolver import create_unique_path_resolver
from yutto.utils.asynclib import sleep_with_status_bar_refresh
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.danmaku import DanmakuOptions
from yutto.utils.fetcher import Fetcher, FetcherContext, create_client
from yutto.utils.funcutils import as_sync
from yutto.utils.time import TIME_FULL_FMT
from yutto.validator import (
    initial_validation,
    validate_basic_arguments,
    validate_batch_arguments,
    validate_user_info,
)

if TYPE_CHECKING:
    import argparse

    from yutto._typing import EpisodeData


def main():
    parser = cli()
    args = parser.parse_args()
    ctx = FetcherContext()
    initial_validation(ctx, args)
    args_list = flatten_args(args, parser)
    try:
        run(ctx, args_list)
    except (SystemExit, KeyboardInterrupt, asyncio.exceptions.CancelledError):
        Logger.info("已终止下载，再次运行即可继续下载～")
        sys.exit(ErrorCode.PAUSED_DOWNLOAD.value)


@as_sync
async def run(ctx: FetcherContext, args_list: list[argparse.Namespace]):
    ctx.set_fetch_semaphore(fetch_workers=8)
    unique_path = create_unique_path_resolver()
    async with create_client(
        cookies=ctx.cookies,
        trust_env=ctx.trust_env,
        proxy=ctx.proxy,
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
            if not await validate_user_info(ctx, {"is_login": args.login_strict, "vip_status": args.vip_strict}):
                Logger.error("启用了严格校验大会员或登录模式，请检查 SESSDATA 或大会员状态！")
                sys.exit(ErrorCode.NOT_LOGIN_ERROR.value)
            # 重定向到可识别的 url
            try:
                url = await Fetcher.get_redirected_url(ctx, client, url)
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
                    download_list = await extractor(ctx, client, args)
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
                if not await validate_user_info(ctx, {"is_login": args.login_strict, "vip_status": args.vip_strict}):
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
                    ctx,
                    client,
                    episode_data,
                    {
                        "require_video": args.require_video,
                        "require_chapter_info": args.require_chapter_info,
                        "video_quality": args.video_quality,
                        "video_download_codec": args.vcodec.split(":")[0],
                        "video_save_codec": args.vcodec.split(":")[1],
                        "video_download_codec_priority": args.download_vcodec_priority,
                        "require_audio": args.require_audio,
                        "audio_quality": args.audio_quality,
                        "audio_download_codec": args.acodec.split(":")[0],
                        "audio_save_codec": args.acodec.split(":")[1],
                        "output_format": args.output_format,
                        "output_format_audio_only": args.output_format_audio_only,
                        "overwrite": args.overwrite,
                        "block_size": int(args.block_size * 1024 * 1024),
                        "num_workers": args.num_workers,
                        "save_cover": args.save_cover,
                        "metadata_format": {
                            "premiered": args.metadata_format_premiered,
                            "dateadded": TIME_FULL_FMT,
                        },
                        "banned_mirrors_pattern": args.banned_mirrors_pattern,
                        "danmaku_options": parse_danmaku_options(args),
                    },
                )
                Logger.new_line()
            Logger.new_line()


def flatten_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[argparse.Namespace]:
    """递归展平列表参数"""
    args = copy.copy(args)
    validate_basic_arguments(args)
    # 查看是否存在于 alias 中
    alias_map: dict[str, str] = args.aliases if args.aliases is not None else {}
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


def ensure_unique_path(episode_data: EpisodeData, unique_name_resolver: Callable[[str], str]) -> EpisodeData:
    original_filename = episode_data["filename"]
    new_name = unique_name_resolver(original_filename)
    episode_data["filename"] = new_name
    if original_filename != new_name:
        Logger.warning(f"文件名重复，已重命名为 {new_name}")
    return episode_data


def parse_danmaku_options(args: argparse.Namespace) -> DanmakuOptions:
    block_options = BlockOptions(
        block_top=args.danmaku_block_top or args.danmaku_block_fixed,
        block_bottom=args.danmaku_block_bottom or args.danmaku_block_fixed,
        block_scroll=args.danmaku_block_scroll,
        block_reverse=args.danmaku_block_reverse,
        block_special=args.danmaku_block_special,
        block_colorful=args.danmaku_block_colorful,
        block_keyword_patterns=(args.danmaku_block_keyword_patterns if args.danmaku_block_keyword_patterns else []),
    )
    return DanmakuOptions(
        font_size=args.danmaku_font_size,
        font=args.danmaku_font,
        opacity=args.danmaku_opacity,
        display_region_ratio=args.danmaku_display_region_ratio,
        speed=args.danmaku_speed,
        block_options=block_options,
    )


if __name__ == "__main__":
    main()
