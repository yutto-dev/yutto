from __future__ import annotations

import asyncio
import copy
import os
import re
import shlex
import sys
from typing import TYPE_CHECKING

from yutto.cli.cli import cli, handle_default_subcommand
from yutto.cli.event_renderer import CliApplicationEventRenderer
from yutto.cli.request_adapter import download_request_from_namespace
from yutto.core.application import YuttoApplication
from yutto.exceptions import ErrorCode, YuttoBaseException
from yutto.input_parser import file_scheme_parser
from yutto.login import run_auth_logout, run_auth_status, run_login
from yutto.utils.console.logger import Logger
from yutto.utils.fetcher import FetcherContext
from yutto.utils.ffmpeg import FFmpegNotFoundError
from yutto.utils.functional import as_sync
from yutto.validator import (
    initial_validation,
    validate_basic_arguments,
)

if TYPE_CHECKING:
    import argparse

    from yutto.core.request import DownloadRequest


def main():
    parser = cli()
    args = parser.parse_args(handle_default_subcommand(sys.argv[1:]))
    match args.command:
        case "download":
            try:
                ctx = FetcherContext()
                initial_validation(ctx, args)
                args_list = flatten_args(args, parser)
                requests = [download_request_from_namespace(item) for item in args_list]
                run_download(ctx, requests)
            except YuttoBaseException as e:
                Logger.error(e.message)
                sys.exit(e.code.value)
            except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
                Logger.info("已终止下载，再次运行即可继续下载～")
                sys.exit(ErrorCode.PAUSED_DOWNLOAD.value)
        case "auth":
            match args.auth_command:
                case "login":
                    run_login(args)
                case "logout":
                    run_auth_logout(args)
                case "status":
                    run_auth_status(args)
                case _:
                    raise ValueError("Invalid auth command")

        case "serve":
            from yutto.server.command import run_server_command

            try:
                run_server_command(args)
            except KeyboardInterrupt:
                Logger.info("yutto server 已停止")
            except (FFmpegNotFoundError, OSError, ValueError) as e:
                Logger.error(str(e))
                sys.exit(ErrorCode.WRONG_ARGUMENT_ERROR.value)

        case _:
            raise ValueError("Invalid command")


@as_sync
async def run_download(ctx: FetcherContext, requests: list[DownloadRequest]):
    application = YuttoApplication(ctx, event_sink=CliApplicationEventRenderer())
    await application.download_all(requests)


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
