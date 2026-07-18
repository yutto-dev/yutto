from __future__ import annotations

import os
import secrets
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING

from yutto.auth import default_auth_file
from yutto.cli.request_adapter import download_request_parser_from_settings
from yutto.core.application import YuttoApplication
from yutto.core.task_service import DownloadTaskService, ResolveTaskService
from yutto.download_manager import DownloadManager
from yutto.server.service import ServerPolicy, ServerPolicyOptions
from yutto.server.websocket import WebSocketServerOptions, YuttoWebSocketServer
from yutto.utils.console.logger import Logger
from yutto.utils.ffmpeg import FFmpeg
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    import argparse
    from collections.abc import Mapping
    from pathlib import Path

    from yutto.core.events import DownloadEventSink
    from yutto.utils.fetcher import FetcherContext


@dataclass(frozen=True, slots=True)
class ServerToken:
    value: str
    generated: bool
    persisted_to: Path | None = None


def resolve_server_token(
    token_file: Path | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ServerToken:
    environment = os.environ if environ is None else environ
    environment_token = environment.get("YUTTO_SERVER_TOKEN", "").strip()
    if environment_token:
        return ServerToken(environment_token, generated=False)

    if token_file is not None:
        try:
            token = _read_server_token(token_file)
        except FileNotFoundError:
            pass
        else:
            return ServerToken(token, generated=False, persisted_to=token_file)

    token = secrets.token_urlsafe(32)
    if token_file is None:
        return ServerToken(token, generated=True)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            token_file,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        existing_token = _read_server_token(token_file)
        return ServerToken(existing_token, generated=False, persisted_to=token_file)
    with os.fdopen(descriptor, "w", encoding="utf-8") as token_stream:
        token_stream.write(token + "\n")
    return ServerToken(token, generated=True, persisted_to=token_file)


def _read_server_token(token_file: Path) -> str:
    try:
        descriptor = os.open(token_file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        raise
    except OSError as error:
        raise ValueError(f"无法安全读取 server token 文件：{token_file}") from error

    with os.fdopen(descriptor, encoding="utf-8") as token_stream:
        metadata = os.fstat(token_stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"server token 路径不是普通文件：{token_file}")
        if os.name != "nt" and metadata.st_mode & 0o077:
            raise ValueError(f"server token 文件权限过宽，请执行 chmod 600：{token_file}")
        token = token_stream.read().strip()
    if not token:
        raise ValueError(f"server token 文件为空：{token_file}")
    return token


def build_server(args: argparse.Namespace, token: str, *, ffmpeg: FFmpeg | None = None) -> YuttoWebSocketServer:
    ffmpeg = ffmpeg or FFmpeg()
    policy = ServerPolicy(
        ServerPolicyOptions(
            download_root=args.download_root,
            tmp_root=args.tmp_root or args.download_root,
            auth_file=args.auth_file or default_auth_file(),
            max_fetch_workers=args.max_fetch_workers,
            max_download_workers=args.max_download_workers,
            allowed_video_save_codecs=frozenset([*ffmpeg.video_encodecs, "copy"]),
            allowed_audio_save_codecs=frozenset([*ffmpeg.audio_encodecs, "copy"]),
        )
    )
    parse_request = download_request_parser_from_settings(args.server_settings)
    default_request = parse_request({"source": {"url": "yutto-server-default-validation"}})
    policy.prepare_request(default_request)
    policy.build_context(default_request)
    task_service = DownloadTaskService(
        policy.build_context,
        _build_download_application,
        task_limit=args.task_limit,
    )
    resolve_service = ResolveTaskService(
        policy.build_context,
        _build_download_application,
        task_limit=args.task_limit,
    )
    return YuttoWebSocketServer(
        task_service,
        WebSocketServerOptions(
            token=token,
            host=args.host,
            port=args.port,
            allowed_origins=tuple(args.allow_origin),
        ),
        prepare_request=policy.prepare_request,
        parse_request=parse_request,
        resolve_service=resolve_service,
    )


def _build_download_application(ctx: FetcherContext, event_sink: DownloadEventSink) -> YuttoApplication:
    manager = DownloadManager()
    return YuttoApplication(ctx, workflow=manager, event_sink=event_sink, resolve_workflow=manager)


@as_sync
async def run_server_command(args: argparse.Namespace) -> None:
    # 与 download 子命令一样，在真正接收任务前确认 FFmpeg 可用。
    ffmpeg = FFmpeg()
    token = resolve_server_token(args.token_file)
    server = build_server(args, token.value, ffmpeg=ffmpeg)
    await server.start()
    for socket in server.sockets:
        address = socket.getsockname()
        display_host = f"[{address[0]}]" if ":" in address[0] else address[0]
        Logger.info(f"yutto server 正在监听 ws://{display_host}:{address[1]}")
    if token.persisted_to is not None:
        Logger.info(f"server token 文件：{token.persisted_to}")
    elif token.generated:
        Logger.info(f"本次 server token：{token.value}")
    try:
        await server.serve_forever()
    finally:
        await server.close(cancel_pending=True)
