import argparse

from yutto.cli import get, info, check_options
from yutto.__version__ import __version__
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.console.colorful import colored_string
from yutto.utils.console.logger import Logger
from yutto.media.quality import video_quality_priority_default, audio_quality_priority_default


def main():
    parser = argparse.ArgumentParser(description="yutto 一个任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s {}".format(__version__))
    parser.add_argument("-n", "--num-workers", type=int, default=8, help="同时下载的 Worker 个数")
    parser.add_argument(
        "-q",
        "--video-quality",
        default=125,
        choices=video_quality_priority_default,
        type=int,
        help="视频清晰度等级（125:HDR, 120:4K, 116:1080P60, 112:1080P+, 80:1080P, 74:720P60, 64:720P, 32:480P, 16:360P）",
    )
    parser.add_argument(
        "--audio-quality",
        default=30280,
        choices=audio_quality_priority_default,
        type=int,
        help="音频码率等级（30280:320kbps, 30232:128kbps, 30216:64kbps）",
    )
    parser.add_argument("--vcodec", default="avc:copy", help="视频编码格式（<下载格式>:<生成格式>）")
    parser.add_argument("--acodec", default="mp4a:copy", help="音频编码格式（<下载格式>:<生成格式>）")
    parser.add_argument("--only-video", dest="require_audio", action="store_false", help="只下载视频")
    parser.add_argument("--only-audio", dest="require_video", action="store_false", help="只下载音频")
    parser.add_argument("--danmaku", default="xml", choices=["xml", "ass", "no"], help="视频主页xxx")
    parser.add_argument("-b", "--block-size", default=1.0, type=float, help="分块下载时各块大小，单位为 MiB，默认为 1MiB")
    parser.add_argument("-w", "--overwrite", action="store_true", help="强制覆盖已下载内容")
    parser.add_argument("-x", "--proxy", default="auto", help="设置代理（auto 为系统代理、no 为不使用代理、当然也可以设置代理值）")
    parser.add_argument("-d", "--dir", default="", help="下载目录")
    parser.add_argument("-c", "--sessdata", default="", help="Cookies 中的 SESSDATA 字段")
    parser.add_argument("--path-pattern", default="{auto}", help="多级目录的存储路径 Pattern")
    parser.add_argument("--no-color", action="store_true", help="不使用颜色")
    parser.add_argument("--debug", action="store_true", help="启用 debug 模式")
    parser.set_defaults(action=run)

    subparsers = parser.add_subparsers()
    # 子命令 get
    parser_get = subparsers.add_parser("get", help="获取单个视频")
    get.add_get_arguments(parser_get)
    # 子命令 info
    # TODO
    # 子命令 batch
    # TODO

    # 执行各自的 action
    args = parser.parse_args()
    check_options.check_basic_options(args)
    args.action(args)


def run(args: argparse.Namespace):
    Logger.error("未指定子命令 (get, info, batch)")
    Logger.info("yutto version: {}".format(colored_string(__version__, fore="green")))
    Logger.info("FFmpeg version: {}".format(colored_string(FFmpeg().version, fore="blue")))


if __name__ == "__main__":
    main()
