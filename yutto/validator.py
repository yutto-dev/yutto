import argparse
import asyncio
import os
import re
import sys

import aiohttp

from yutto.api.info import is_vip
from yutto.exceptions import ErrorCode
from yutto.bilibili_typing.codec import audio_codec_priority_default, video_codec_priority_default
from yutto.processor.selector import validate_episodes_selection
from yutto.utils.asynclib import initial_async_policy, install_uvloop
from yutto.utils.console.colorful import set_no_color
from yutto.utils.console.logger import Badge, Logger, set_logger_debug
from yutto.utils.fetcher import Fetcher
from yutto.utils.ffmpeg import FFmpeg


def initial_validate(args: argparse.Namespace):
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
    else:
        # 为保证协程错误栈的可读性，debug 模式不启用 uvloop
        install_uvloop()

    # 初始化异步策略，消除平台差异
    initial_async_policy()

    # proxy 校验
    if args.proxy not in ["no", "auto"] and not re.match(r"https?://", args.proxy):
        Logger.error("proxy 参数值（{}）错误啦！".format(args.proxy))
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)
    Fetcher.set_proxy(args.proxy)

    # 大会员身份校验
    if not args.sessdata:
        Logger.info("未提供 SESSDATA，无法下载会员专享剧集哟～")
    else:
        Fetcher.set_sessdata(args.sessdata)
        if asyncio.run(vip_validate()):
            Logger.custom("成功以大会员身份登录～", badge=Badge("大会员", fore="white", back="magenta", style=["bold"]))
        else:
            Logger.warning("以非大会员身份登录，注意无法下载会员专享剧集喔～")


def validate_basic_arguments(args: argparse.Namespace):
    """检查 argparse 无法检查的选项，并设置某些全局的状态"""

    ffmpeg = FFmpeg()

    # vcodec 检查
    vcodec_splited = args.vcodec.split(":")
    if len(vcodec_splited) != 2:
        Logger.error("vcodec 参数值（{}）不满足要求哦（并非使用 : 分隔的值）".format(args.vcodec))
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
        Logger.error("acodec 参数值（{}）不满足要求哦（并非使用 : 分隔的值）".format(args.acodec))
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

    # video_only 和 audio_only 不能同时设置
    if not args.require_video and not args.require_audio:
        Logger.error("video_only 和 audio_only 不能同时设置呀！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 不下载视频无法嵌入字幕
    if not args.require_video and args.embed_subtitle:
        Logger.error("不下载视频时无法嵌入字幕的哦！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 不下载视频无法嵌入弹幕
    if not args.require_video and args.embed_danmaku:
        Logger.error("不下载视频时无法嵌入弹幕的哦！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 不下载视频无法生成 ASS 弹幕（ASS 弹幕生成计算依赖于视频分辨率大小）
    if not args.require_video and not args.no_danmaku and args.danmaku_format == "ass":
        Logger.error("不下载视频无法生成 ASS 弹幕呀！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 生成字幕才可以嵌入字幕
    if args.embed_subtitle and args.no_subtitle:
        Logger.error("生成字幕才可以嵌入字幕喔！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 生成 ASS 弹幕才可以嵌入弹幕
    if args.embed_danmaku and args.no_danmaku:
        Logger.error("生成 ASS 弹幕才可以嵌入弹幕喔！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

    # 嵌入弹幕功能仅支持 ASS 弹幕
    if args.embed_danmaku and args.danmaku_format != "ass":
        Logger.error("嵌入弹幕功能仅支持 ASS 弹幕喔！")
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)


def validate_batch_argments(args: argparse.Namespace):
    """检查批量下载相关选项"""
    # 检查 episodes 格式（简单的正则检查，后续过滤剧集时还有完整检查）
    if not validate_episodes_selection(args.episodes):
        # TODO: 错误信息链接到相应文档，当然需要先写文档……
        Logger.error("选集参数（{}）格式不正确呀～重新检查一下下～".format(args.episodes))
        sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)


async def vip_validate() -> bool:
    async with aiohttp.ClientSession(
        headers=Fetcher.headers,
        cookies=Fetcher.cookies,
        trust_env=Fetcher.trust_env,
        timeout=aiohttp.ClientTimeout(total=5),
    ) as session:
        return await is_vip(session)
