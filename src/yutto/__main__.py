from __future__ import annotations

import asyncio
import copy
import os
import re
import shlex
import sys
from typing import TYPE_CHECKING

from yutto.cli.cli import cli, handle_default_subcommand
from yutto.download_manager import DownloadManager, DownloadTask
from yutto.exceptions import ErrorCode
from yutto.input_parser import file_scheme_parser
from yutto.login import run_login
from yutto.utils.console.logger import Badge, Logger
from yutto.utils.fetcher import FetcherContext
from yutto.utils.functional import as_sync
from yutto.validator import (
    initial_validation,
    validate_basic_arguments,
)

if TYPE_CHECKING:
    import argparse


def main():
    parser = cli()
    args = parser.parse_args(handle_default_subcommand(sys.argv[1:]))
    match args.command:
        case "download":
            ctx = FetcherContext()
            initial_validation(ctx, args)
            args_list = flatten_args(args, parser)
            try:
                run_download(ctx, args_list)
            except (SystemExit, KeyboardInterrupt, asyncio.exceptions.CancelledError):
                Logger.info("已终止下载，再次运行即可继续下载～")
                sys.exit(ErrorCode.PAUSED_DOWNLOAD.value)
        case "mcp":
            from yutto.mcp_server import run_mcp

            run_mcp()
        case "login":
            run_login(args)

        case _:
            raise ValueError("Invalid command")


@as_sync
async def run_download(ctx: FetcherContext, args_list: list[argparse.Namespace]):
    manager = DownloadManager()
    manager.start(ctx)
    if len(args_list) > 1:
        Logger.info(f"列表里共检测到 {len(args_list)} 项")

    for i, args in enumerate(args_list):
        if len(args_list) > 1:
            Logger.custom(f"列表项 {args.url}", Badge(f"[{i + 1}/{len(args_list)}]", fore="black", back="cyan"))
        await manager.add_task(DownloadTask(args=args))
    await manager.add_stop_task()
    await manager.wait_for_completion()


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
            local_args = parser.parse_args(handle_default_subcommand(shlex.split(line)), args)
            if local_args.no_inherit:
                local_args = parser.parse_args(handle_default_subcommand(shlex.split(line)))
            Logger.debug(f"列表参数: {local_args}")
            args_list += flatten_args(local_args, parser)
        return args_list
    else:
        return [args]


if __name__ == "__main__":
    main()
