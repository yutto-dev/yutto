from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

import aiohttp

from yutto.api.user_info import is_vip
from yutto.bilibili_typing.codec import (
    audio_codec_priority_default,
    video_codec_priority_default,
)
from yutto.exceptions import ErrorCode
from yutto.processor.selector import validate_episodes_selection
from yutto.utils.asynclib import initial_async_policy
from yutto.utils.console.colorful import set_no_color
from yutto.utils.console.logger import Badge, Logger, set_logger_debug
from yutto.utils.fetcher import Fetcher
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.filter import Filter


def initial_validation(args: argparse.Namespace):
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

    # 初始化异步策略，消除平台差异
    initial_async_policy()

    # proxy 校验
    if args.proxy not in ["no", "auto"] and not re.match(r"https?://", args.proxy):
        Logger.error(f"proxy 参数值（{args.proxy}）错误啦！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    Fetcher.set_proxy(args.proxy)

    # 大会员身份校验
    if not args.sessdata:
        Logger.info("未提供 SESSDATA，无法下载会员专享剧集哟～")
    else:
        Fetcher.set_sessdata(args.sessdata)
        if asyncio.run(validate_vip()):
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

    # vcodec 检查
    vcodec_splited = args.vcodec.split(":")
    if len(vcodec_splited) != 2:
        Logger.error(f"vcodec 参数值（{args.vcodec}）不满足要求哦（并非使用 : 分隔的值）")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    video_download_codec, video_save_codec = vcodec_splited
    if video_download_codec not in video_codec_priority_default:
        Logger.error(
            "download_vcodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                video_download_codec, ", ".join(video_codec_priority_default)
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    if video_save_codec not in ffmpeg.video_encodecs + ["copy"]:
        Logger.error(
            "save_vcodec 参数值（{}）不满足要求哦（允许值：{{{}}}）".format(
                video_save_codec, ", ".join(ffmpeg.video_encodecs + ["copy"])
            )
        )
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # acodec 检查
    acodec_splited = args.acodec.split(":")
    if len(acodec_splited) != 2:
        Logger.error(f"acodec 参数值（{args.acodec}）不满足要求哦（并非使用 : 分隔的值）")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    audio_download_codec, audio_save_codec = acodec_splited
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


def validate_batch_argments(args: argparse.Namespace):
    """检查批量下载相关选项"""
    # 检查 episodes 格式（简单的正则检查，后续过滤剧集时还有完整检查）
    if not validate_episodes_selection(args.episodes):
        # TODO: 错误信息链接到相应文档，当然需要先写文档……
        Logger.error(f"选集参数（{args.episodes}）格式不正确呀～重新检查一下下～")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)


async def validate_vip() -> bool:
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        return await is_vip(session)
