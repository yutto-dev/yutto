import argparse
import re
import os
import copy

from yutto.__version__ import VERSION as yutto_version
from yutto.cli import batch_get, checker, get
from yutto.media.quality import audio_quality_priority_default, video_quality_priority_default
from yutto.processor.urlparser import alias_parser, file_scheme_parser, bare_name_parser
from yutto.utils.console.logger import Logger, Badge


def main():
    parser = argparse.ArgumentParser(description="yutto 一个可爱且任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s {}".format(yutto_version))
    parser.add_argument("url", help="视频主页 url 或 url 列表（需使用 file scheme）")
    group_common = parser.add_argument_group("common", "通用参数")
    group_common.add_argument("-n", "--num-workers", type=int, default=8, help="同时用于下载的最大 Worker 数")
    group_common.add_argument(
        "-q",
        "--video-quality",
        default=125,
        choices=video_quality_priority_default,
        type=int,
        help="视频清晰度等级（125:HDR, 120:4K, 116:1080P60, 112:1080P+, 80:1080P, 74:720P60, 64:720P, 32:480P, 16:360P）",
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
    group_common.add_argument("-c", "--sessdata", default="", help="Cookies 中的 SESSDATA 字段")
    group_common.add_argument("-tp", "--subpath-template", default="{auto}", help="多级目录的存储路径模板")
    group_common.add_argument(
        "-af", "--alias-file", type=argparse.FileType("r", encoding="utf-8"), help="设置 url 别名文件路径"
    )
    group_common.add_argument("--no-danmaku", action="store_true", help="不生成弹幕文件")
    group_common.add_argument("--no-subtitle", action="store_true", help="不生成字幕文件")
    group_common.add_argument("--embed-danmaku", action="store_true", help="（待实现）将弹幕文件嵌入到视频中")
    group_common.add_argument("--embed-subtitle", default=None, help="（待实现）将字幕文件嵌入到视频中（需输入语言代码）")
    group_common.add_argument("--no-color", action="store_true", help="不使用颜色")
    group_common.add_argument("--debug", action="store_true", help="启用 debug 模式")

    # 仅批量下载使用
    group_batch = parser.add_argument_group("batch", "批量下载参数")
    group_batch.add_argument("-b", "--batch", action="store_true", help="批量下载")
    group_batch.add_argument("-p", "--episodes", default="^~$", help="选集")
    group_batch.add_argument("-s", "--with-section", action="store_true", help="同时下载附加剧集（PV、预告以及特别篇等专区内容）")

    # 仅 file scheme 列表中使用
    group_batch_file = parser.add_argument_group("batch file", "批量下载文件参数")
    group_batch_file.add_argument("--no-inherit", action="store_true", help="不继承父级参数")

    # 执行各自的 run
    args = parser.parse_args()
    checker.initial_check(args)
    args_list = flatten_args(args, parser)
    if len(args_list) > 1:
        Logger.info(f"列表共 {len(args_list)} 项")
    for i, args in enumerate(args_list):
        if len(args_list) > 1:
            Logger.custom(f"列表项 {args.url}", Badge(f"[{i+1}/{len(args_list)}]", fore="black", back="cyan"))
        if not args.batch:
            get.run(args)
        else:
            checker.check_batch_argments(args)
            batch_get.run(args)
        Logger.print("")


def flatten_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[argparse.Namespace]:
    """递归展平列表参数"""
    args = copy.copy(args)
    checker.check_basic_arguments(args)
    # 查看是否存在于 alias 中
    alias_map = alias_parser(args.alias_file)
    if args.url in alias_map:
        args.url = alias_map[args.url]
    args.url = bare_name_parser(args.url)

    # 是否为下载列表
    if re.match(r"file://", args.url) or os.path.exists(args.url):
        args_list: list[argparse.Namespace] = []
        # TODO: 如果是相对路径，需要相对于当前 list 路径
        for line in file_scheme_parser(args.url):
            local_args = parser.parse_args(line.split(), args)
            if local_args.no_inherit:
                local_args = parser.parse_args(line.split())
            Logger.debug("列表参数: {}".format(local_args))
            args_list += flatten_args(local_args, parser)
        return args_list
    else:
        return [args]


if __name__ == "__main__":
    main()
