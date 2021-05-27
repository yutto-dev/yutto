import argparse
import sys

from yutto.__version__ import VERSION as yutto_version
from yutto.cli import basic, batch_get, check_options, get, info
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.ffmpeg import FFmpeg


def main():
    parser = argparse.ArgumentParser(description="yutto 一个可爱且任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s {}".format(yutto_version))

    subparsers = parser.add_subparsers()
    # 子命令 get
    parser_get = subparsers.add_parser("get", help="获取单个视频")
    basic.add_basic_arguments(parser_get)
    get.add_arguments(parser_get)
    # 子命令 info
    # TODO
    # 子命令 batch
    parser_batch = subparsers.add_parser("batch", help="批量获取视频（需使用其子命令 get/info）")
    subparsers_batch = parser_batch.add_subparsers()
    # 子命令 batch get
    parser_batch_get = subparsers_batch.add_parser("get", help="批量获取视频")
    basic.add_basic_arguments(parser_batch_get)
    batch_get.add_arguments(parser_batch_get)
    # 子命令 batch info
    # TODO
    # 执行各自的 action
    args = parser.parse_args()
    if "action" in args:
        check_options.check_basic_options(args)
        args.action(args)
    else:
        Logger.error("未指定子命令 (get, info, batch)")
        python_version = "{}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2])
        ffmpeg_version = FFmpeg().version
        Logger.print(
            Badge("Python", fore="black", back="green"), Badge(python_version, fore="green", back="black"), sep=""
        )
        Logger.print(Badge("yutto", fore="black", back="blue"), Badge(yutto_version, fore="blue", back="black"), sep="")
        Logger.print(
            Badge("ffmpeg", fore="black", back="cyan"), Badge(ffmpeg_version, fore="cyan", back="black"), sep=""
        )
        parser.print_help()


if __name__ == "__main__":
    main()
