from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any, Literal

from yutto.__version__ import VERSION as yutto_version
from yutto.bilibili_typing.quality import (
    audio_quality_priority_default,
    video_quality_priority_default,
)
from yutto.cli.settings import YuttoSettings, load_settings_file, search_for_settings_file
from yutto.processor.parser import alias_parser, path_from_cli
from yutto.utils.console.logger import Logger
from yutto.utils.funcutils.option import map_some

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from typing_extensions import TypeAlias


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


def parse_config_path() -> Path | None:
    pre_parser = argparse.ArgumentParser(description="yutto pre parser", add_help=False)
    pre_parser.add_argument("--config", type=path_from_cli, default=search_for_settings_file(), help="配置文件路径")
    args, _ = pre_parser.parse_known_args()
    return args.config


def cli() -> argparse.ArgumentParser:
    settings_file = parse_config_path()
    if settings_file is None:
        settings = YuttoSettings()  # pyright: ignore[reportCallIssue]
    else:
        Logger.info(f"发现配置文件 {settings_file}，加载中……")
        settings = load_settings_file(settings_file)

    parser = argparse.ArgumentParser(description="yutto 一个可爱且任性的 B 站视频下载器", prog="yutto")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {yutto_version}")
    # 如果需要创建其他子命令可参考
    # https://stackoverflow.com/questions/29998417/create-parser-with-subcommands-in-argparse-customize-positional-arguments
    parser.add_argument("url", help="视频主页 url 或 url 列表（需使用 file scheme）")
    group_basic = parser.add_argument_group("basic", "基础参数")
    group_basic.add_argument(
        "-n", "--num-workers", type=int, default=settings.basic.num_workers, help="同时用于下载的最大 Worker 数"
    )
    group_basic.add_argument(
        "-q",
        "--video-quality",
        default=settings.basic.video_quality,
        choices=video_quality_priority_default,
        type=int,
        help="视频清晰度等级（127:8K, 126:Dolby Vision, 125:HDR, 120:4K, 116:1080P60, 112:1080P+, 100:智能修复, 80:1080P, 74:720P60, 64:720P, 32:480P, 16:360P）",
    )
    group_basic.add_argument(
        "-aq",
        "--audio-quality",
        default=settings.basic.audio_quality,
        choices=audio_quality_priority_default,
        type=int,
        help="音频码率等级（30251:Hi-Res, 30255:Dolby Audio, 30250:Dolby Atmos, 30280:320kbps, 30232:128kbps, 30216:64kbps）",
    )
    group_basic.add_argument(
        "--vcodec",
        default=settings.basic.vcodec,
        metavar="DOWNLOAD_VCODEC:SAVE_VCODEC",
        help="视频编码格式（<下载格式>:<生成格式>）",
    )
    group_basic.add_argument(
        "--acodec",
        default=settings.basic.acodec,
        metavar="DOWNLOAD_ACODEC:SAVE_ACODEC",
        help="音频编码格式（<下载格式>:<生成格式>）",
    )
    group_basic.add_argument(
        "--download-vcodec-priority",
        default=settings.basic.download_vcodec_priority,
        type=lambda codecs: codecs.split(",") if codecs != "auto" else None,
        help="视频编码格式优先级，使用 `,` 分隔，如 `hevc,avc,av1`，默认为 `auto`，即根据 vcodec 中「下载编码」自动推断",
    )
    group_basic.add_argument(
        "--output-format",
        default=settings.basic.output_format,
        choices=["infer", "mp4", "mkv", "mov"],
        help="输出格式（infer 为自动推断）",
    )
    group_basic.add_argument(
        "--output-format-audio-only",
        default=settings.basic.output_format_audio_only,
        choices=["infer", "aac", "mp3", "flac", "mp4", "mkv", "mov"],
        help="仅包含音频流时所使用的输出格式（infer 为自动推断）",
    )
    group_basic.add_argument(
        "-df",
        "--danmaku-format",
        default=settings.basic.danmaku_format,
        choices=["xml", "ass", "protobuf"],
        help="弹幕类型",
    )
    group_basic.add_argument(
        "-bs",
        "--block-size",
        default=settings.basic.block_size,
        type=float,
        help="分块下载时各块大小，单位为 MiB，默认为 0.5MiB",
    )
    group_basic.add_argument(
        "-w", "--overwrite", default=settings.basic.overwrite, action="store_true", help="强制覆盖已下载内容"
    )
    group_basic.add_argument(
        "-x",
        "--proxy",
        default=settings.basic.proxy,
        help="设置代理（auto 为系统代理、no 为不使用代理、当然也可以设置代理值）",
    )
    group_basic.add_argument(
        "-d",
        "--dir",
        default=path_from_cli(settings.basic.dir),
        type=path_from_cli,
        help="下载目录，默认为运行目录",
    )
    group_basic.add_argument(
        "--tmp-dir",
        default=map_some(path_from_cli, settings.basic.tmp_dir),
        type=path_from_cli,
        help="用来存放下载过程中临时文件的目录，默认为下载目录",
    )
    group_basic.add_argument("-c", "--sessdata", default=settings.basic.sessdata, help="Cookies 中的 SESSDATA 字段")
    group_basic.add_argument(
        "-tp", "--subpath-template", default=settings.basic.subpath_template, help="多级目录的存储路径模板"
    )
    group_basic.add_argument(
        "-af",
        "--alias-file",
        dest="aliases",
        type=alias_parser,
        default=settings.basic.aliases,
        help="设置 url 别名文件路径",
    )
    group_basic.add_argument(
        "--metadata-format-premiered",
        default=settings.basic.metadata_format_premiered,
        help="专用于 metadata 文件中 premiered 字段的日期格式",
    )
    group_basic.add_argument(
        "--download-interval", default=settings.basic.download_interval, type=int, help="设置下载间隔，单位为秒"
    )
    group_basic.add_argument(
        "--banned-mirrors-pattern",
        default=settings.basic.banned_mirrors_pattern,
        help="禁用下载链接的镜像源，使用正则匹配",
    )
    group_basic.add_argument("--no-color", default=settings.basic.no_color, action="store_true", help="不使用颜色")
    group_basic.add_argument(
        "--no-progress", default=settings.basic.no_progress, action="store_true", help="不显示进度条"
    )
    group_basic.add_argument("--debug", default=settings.basic.debug, action="store_true", help="启用 debug 模式")
    group_basic.add_argument(
        "--vip-strict", default=settings.basic.vip_strict, action="store_true", help="启用严格检查大会员生效"
    )
    group_basic.add_argument(
        "--login-strict", default=settings.basic.login_strict, action="store_true", help="启用严格检查登录状态"
    )

    # 资源选择
    group_resource = parser.add_argument_group("resource", "资源选择参数")
    group_resource.add_argument(
        "--video-only",
        dest="require_audio",
        action=create_select_required_action(deselect=["audio"]),
        help="仅下载视频流",
    )
    group_resource.add_argument(
        "--audio-only",
        dest="require_video",
        action=create_select_required_action(deselect=["video"]),
        help="仅下载音频流",
    )  # 视频和音频是反选对方，而不是其余反选所有的
    group_resource.add_argument(
        "--no-danmaku",
        dest="require_danmaku",
        action=create_select_required_action(deselect=["danmaku"]),
        help="不生成弹幕文件",
    )
    group_resource.add_argument(
        "--danmaku-only",
        dest="require_danmaku",
        action=create_select_required_action(select=["danmaku"], deselect=invert_selection(["danmaku"])),
        help="仅生成弹幕文件",
    )
    group_resource.add_argument(
        "--no-subtitle",
        dest="require_subtitle",
        action=create_select_required_action(deselect=["subtitle"]),
        help="不生成字幕文件",
    )
    group_resource.add_argument(
        "--subtitle-only",
        dest="require_subtitle",
        action=create_select_required_action(select=["subtitle"], deselect=invert_selection(["subtitle"])),
        help="仅生成字幕文件",
    )
    group_resource.add_argument(
        "--with-metadata",
        dest="require_metadata",
        action=create_select_required_action(select=["metadata"]),
        help="生成元数据文件",
    )
    group_resource.add_argument(
        "--metadata-only",
        dest="require_metadata",
        action=create_select_required_action(select=["metadata"], deselect=invert_selection(["metadata"])),
        help="仅生成元数据文件",
    )
    group_resource.add_argument(
        "--no-cover",
        dest="require_cover",
        action=create_select_required_action(deselect=["cover"]),
        help="不生成封面",
    )
    group_resource.add_argument(
        "--cover-only",
        dest="require_cover",
        action=create_select_required_action(select=["cover"], deselect=invert_selection(["cover"])),
        help="仅生成封面",
    )
    group_resource.add_argument(
        "--no-chapter-info",
        dest="require_chapter_info",
        action=create_select_required_action(deselect=["chapter_info"]),
        help="不封装章节信息",
    )
    group_resource.add_argument(
        "--save-cover",
        default=settings.resource.save_cover,
        action="store_true",
        help="生成视频流封面后单独保存封面文件",
    )
    group_resource.set_defaults(
        require_video=settings.resource.require_video,
        require_audio=settings.resource.require_audio,
        require_subtitle=settings.resource.require_subtitle,
        require_metadata=settings.resource.require_metadata,
        require_danmaku=settings.resource.require_danmaku,
        require_cover=settings.resource.require_cover,
        require_chapter_info=settings.resource.require_chapter_info,
    )

    # 弹幕设置
    group_danmaku = parser.add_argument_group("danmaku", "弹幕设置参数")
    group_danmaku.add_argument("--danmaku-font-size", type=int, default=settings.danmaku.font_size, help="弹幕字体大小")
    group_danmaku.add_argument("--danmaku-font", default=settings.danmaku.font, help="弹幕字体")
    group_danmaku.add_argument("--danmaku-opacity", type=float, default=settings.danmaku.opacity, help="弹幕不透明度")
    group_danmaku.add_argument(
        "--danmaku-display-region-ratio",
        help="弹幕显示区域与视频高度的比例",
        type=float,
        default=settings.danmaku.display_region_ratio,
    )
    group_danmaku.add_argument("--danmaku-speed", help="弹幕速度", type=float, default=settings.danmaku.speed)
    group_danmaku.add_argument(
        "--danmaku-block-top", action="store_true", default=settings.danmaku.block_top, help="屏蔽顶部弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-bottom", default=settings.danmaku.block_bottom, action="store_true", help="屏蔽底部弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-scroll", default=settings.danmaku.block_scroll, action="store_true", help="屏蔽滚动弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-reverse", default=settings.danmaku.block_reverse, action="store_true", help="屏蔽逆向弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-fixed",
        default=settings.danmaku.block_fixed,
        action="store_true",
        help="屏蔽固定弹幕（顶部、底部）",
    )
    group_danmaku.add_argument(
        "--danmaku-block-special", default=settings.danmaku.block_special, action="store_true", help="屏蔽高级弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-colorful", default=settings.danmaku.block_colorful, action="store_true", help="屏蔽彩色弹幕"
    )
    group_danmaku.add_argument(
        "--danmaku-block-keyword-patterns",
        default=settings.danmaku.block_keyword_patterns,
        type=lambda patterns: [pattern.strip() for pattern in patterns.split(",")],
        help="屏蔽匹配关键词的弹幕，使用逗号分隔",
    )

    # 仅批量下载使用
    group_batch = parser.add_argument_group("batch", "批量下载参数")
    group_batch.add_argument("-b", "--batch", action="store_true", help="批量下载")
    group_batch.add_argument("-p", "--episodes", default="1~-1", help="选集")
    group_batch.add_argument(
        "-s",
        "--with-section",
        action="store_true",
        default=settings.batch.with_section,
        help="同时下载附加剧集（PV、预告以及特别篇等专区内容）",
    )
    group_batch.add_argument(
        "--batch-filter-start-time",
        default=settings.batch.batch_filter_start_time,
        help="只下载该时间之后（包含临界值）发布的稿件",
    )
    group_batch.add_argument(
        "--batch-filter-end-time",
        default=settings.batch.batch_filter_end_time,
        help="只下载该时间之前（不包含临界值）发布的稿件",
    )

    # 仅任务列表中使用
    group_batch_file = parser.add_argument_group("batch file", "批量下载文件参数")
    group_batch_file.add_argument("--no-inherit", action="store_true", help="不继承父级参数")

    # 配置路径（占位用的，config 已经在 pre parser 里解析过了）
    group_config = parser.add_argument_group("config", "配置文件参数")
    group_config.add_argument("--config", help="配置文件路径")

    return parser


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
