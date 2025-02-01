from __future__ import annotations

import asyncio
import os
import re
import sys
from typing import TYPE_CHECKING

import biliass

from yutto.api.user_info import get_user_info
from yutto.bilibili_typing.codec import VideoCodec, audio_codec_priority_default, video_codec_priority_default
from yutto.exceptions import ErrorCode
from yutto.processor.selector import validate_episodes_selection
from yutto.utils.asynclib import initial_async_policy
from yutto.utils.console.colorful import set_no_color
from yutto.utils.console.logger import Badge, Logger, set_logger_debug
from yutto.utils.fetcher import FetcherContext, create_client
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.filter import Filter

if TYPE_CHECKING:
    import argparse

    from yutto._typing import UserInfo


def initial_validation(ctx: FetcherContext, args: argparse.Namespace):
    """初始化检查，仅执行一次"""

    if not args.no_progress:
        Logger.enable_statusbar()

    # 在使用 --no-color 或者环境变量 NO_COLOR 非空时都应该不显示颜色
    # See also: https://no-color.org/
    if args.no_color or os.environ.get("NO_COLOR"):
        set_no_color()

    # debug 设置
    if args.debug:
        set_logger_debug()
        biliass.enable_tracing()

    # 初始化异步策略，消除平台差异
    initial_async_policy()

    # proxy 校验
    if args.proxy not in ["no", "auto"] and not re.match(r"https?://", args.proxy):
        Logger.error(f"proxy 参数值（{args.proxy}）错误啦！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    ctx.set_proxy(args.proxy)

    # 大会员身份校验
    if not args.sessdata:
        Logger.info("未提供 SESSDATA，无法下载高清视频、字幕等资源哦～")
    else:
        ctx.set_sessdata(args.sessdata)
        if asyncio.run(validate_user_info(ctx, {"vip_status": True, "is_login": True})):
            Logger.custom("成功以大会员身份登录～", badge=Badge("大会员", fore="white", back="magenta", style=["bold"]))
        else:
            Logger.warning("以非大会员身份登录，注意无法下载会员专享剧集喔～")

    # 批量下载时的过滤器设置
    if args.batch_filter_start_time:
        Filter.set_timer("batch_filter_start_time", args.batch_filter_start_time)
    if args.batch_filter_end_time:
        Filter.set_timer("batch_filter_end_time", args.batch_filter_end_time)


def validate_basic_arguments(args: argparse.Namespace):
    """检查 argparse 无法检查的选项，并设置某些全局的状态"""

    ffmpeg = FFmpeg()

    download_vcodec_priority: list[VideoCodec] = video_codec_priority_default
    if args.download_vcodec_priority is not None:
        user_download_vcodec_priority = args.download_vcodec_priority
        if not user_download_vcodec_priority:
            Logger.error("download_vcodec_priority 参数值为空哦")
            sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
        for vcodec in user_download_vcodec_priority:
            if vcodec not in video_codec_priority_default:
                Logger.error(
                    "download_vcodec_priority 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                        vcodec, ", ".join(video_codec_priority_default)
                    )
                )
                sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
        download_vcodec_priority = user_download_vcodec_priority
        if len(download_vcodec_priority) < len(video_codec_priority_default):
            Logger.warning(
                "download_vcodec_priority（{}）不包含所有下载视频编码（{}），不包含部分将永远不会选择哦".format(
                    ", ".join(args.download_vcodec_priority), ", ".join(video_codec_priority_default)
                )
            )

    # vcodec 检查
    vcodec_split = args.vcodec.split(":")
    if len(vcodec_split) != 2:
        Logger.error(f"vcodec 参数值（{args.vcodec}）不满足要求哦（并非使用 : 分隔的值）")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    video_download_codec, video_save_codec = vcodec_split
    if video_download_codec not in download_vcodec_priority:
        Logger.error(
            "download_vcodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                video_download_codec, ", ".join(download_vcodec_priority)
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    if args.download_vcodec_priority is not None and download_vcodec_priority[0] != video_download_codec:
        Logger.warning(
            f"download_vcodec 参数值（{video_download_codec}）不是优先级最高的编码（{download_vcodec_priority[0]}），可能会导致下载失败哦"
        )
    if video_save_codec not in ffmpeg.video_encodecs + ["copy"]:
        Logger.error(
            "save_vcodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                video_save_codec, ", ".join(ffmpeg.video_encodecs + ["copy"])
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # acodec 检查
    acodec_split = args.acodec.split(":")
    if len(acodec_split) != 2:
        Logger.error(f"acodec 参数值（{args.acodec}）不满足要求哦（并非使用 : 分隔的值）")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    audio_download_codec, audio_save_codec = acodec_split
    if audio_download_codec not in audio_codec_priority_default:
        Logger.error(
            "download_acodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                audio_download_codec, ", ".join(audio_codec_priority_default)
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    if audio_save_codec not in ffmpeg.audio_encodecs + ["copy"]:
        Logger.error(
            "save_acodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                audio_save_codec, ", ".join(ffmpeg.audio_encodecs + ["copy"])
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # cover 检查
    if not args.require_cover and args.save_cover:
        Logger.warning("没有下载封面的情况下是无法保留封面的哦～")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)


def validate_batch_arguments(args: argparse.Namespace):
    """检查批量下载相关选项"""
    # 检查 episodes 格式（简单的正则检查，后续过滤剧集时还有完整检查）
    if not validate_episodes_selection(args.episodes):
        # TODO: 错误信息链接到相应文档，当然需要先写文档……
        Logger.error(f"选集参数（{args.episodes}）格式不正确呀～重新检查一下下～")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)


async def validate_user_info(ctx: FetcherContext, check_option: UserInfo) -> bool:
    """UserInfo 结构和用户输入是匹配的，如果要校验则置 True 即可，估计不会有要校验为 False 的情况吧~~"""
    async with create_client(
        cookies=ctx.cookies,
        trust_env=ctx.trust_env,
        proxy=ctx.proxy,
    ) as client:
        if check_option["is_login"] or check_option["vip_status"]:
            # 需要校验
            # 这么写 if 是为了少一个 get_user_info 请求
            user_info = await get_user_info(ctx, client)
            if check_option["is_login"] and not user_info["is_login"]:
                return False
            if check_option["vip_status"] and not user_info["vip_status"]:
                return False
        return True
