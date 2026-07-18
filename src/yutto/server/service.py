from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING, TypeAlias, TypeVar

from pydantic import BaseModel

from yutto.auth import load_auth
from yutto.utils.fetcher import FetcherContext, sanitize_proxy_url

if TYPE_CHECKING:
    from yutto.core.request import DownloadRequest
    from yutto.runtime import EventReplay, TaskEvent, TaskSnapshot

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
PayloadT = TypeVar("PayloadT")
ResultT = TypeVar("ResultT")

_CREDENTIAL_FIELDS = frozenset(
    {
        "api_key",
        "auth",
        "authorization",
        "bili_jct",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "password",
        "secret",
        "sessdata",
        "token",
    }
)


class ServerPolicyError(ValueError):
    """A request violates a local server boundary."""


@dataclass(frozen=True, slots=True)
class ServerPolicyOptions:
    """Filesystem, authentication, and concurrency boundaries for the server."""

    download_root: Path
    tmp_root: Path
    auth_file: Path
    max_fetch_workers: int = 8
    max_download_workers: int = 8
    min_block_size_bytes: int = 64 * 1024
    max_block_size_bytes: int = 64 * 1024 * 1024
    allowed_video_save_codecs: frozenset[str] | None = None
    allowed_audio_save_codecs: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.max_fetch_workers < 1:
            raise ValueError("max_fetch_workers must be at least 1")
        if self.max_download_workers < 1:
            raise ValueError("max_download_workers must be at least 1")
        if self.min_block_size_bytes < 1:
            raise ValueError("min_block_size_bytes must be at least 1")
        if self.max_block_size_bytes < self.min_block_size_bytes:
            raise ValueError("max_block_size_bytes must be at least min_block_size_bytes")

        object.__setattr__(self, "download_root", self.download_root.expanduser().resolve())
        object.__setattr__(self, "tmp_root", self.tmp_root.expanduser().resolve())
        object.__setattr__(self, "auth_file", self.auth_file.expanduser().resolve())


class ServerPolicy:
    """Apply server-owned limits before a download enters the task runtime."""

    def __init__(self, options: ServerPolicyOptions):
        self.options = options

    def prepare_request(self, request: DownloadRequest) -> DownloadRequest:
        """Return an immutable copy with server-owned absolute output paths."""
        self._validate_workers(request)
        self._validate_block_size(request)
        self._validate_save_codecs(request)
        self._validate_subpath_template(request.output.subpath_template)
        output_directory = self._resolve_request_path(
            request.output.directory,
            root=self.options.download_root,
            field="output.directory",
        )
        temporary_directory = (
            self.options.tmp_root
            if request.output.temporary_directory is None
            else self._resolve_request_path(
                request.output.temporary_directory,
                root=self.options.tmp_root,
                field="output.temporary_directory",
            )
        )
        output = request.output.model_copy(
            update={
                "directory": output_directory,
                "temporary_directory": temporary_directory,
                "enforce_directory_boundary": True,
            }
        )
        return request.model_copy(update={"output": output})

    def build_context(self, request: DownloadRequest) -> FetcherContext:
        """Build a fetch context without attaching credentials to the request."""
        self._validate_workers(request)
        context = FetcherContext()
        try:
            context.set_proxy(request.network.proxy)
            auth = load_auth(self.options.auth_file, request.access.auth_profile)
        except ValueError as error:
            raise ServerPolicyError(str(error)) from error

        context.set_fetch_workers(request.network.fetch_workers)
        if auth is not None:
            context.set_auth_info(auth)
        return context

    def _validate_workers(self, request: DownloadRequest) -> None:
        self._validate_worker_count(
            "network.fetch_workers",
            request.network.fetch_workers,
            self.options.max_fetch_workers,
        )
        self._validate_worker_count(
            "network.download_workers",
            request.network.download_workers,
            self.options.max_download_workers,
        )

    def _validate_block_size(self, request: DownloadRequest) -> None:
        value = request.network.block_size_bytes
        if not self.options.min_block_size_bytes <= value <= self.options.max_block_size_bytes:
            raise ServerPolicyError(
                "network.block_size_bytes must be between "
                f"{self.options.min_block_size_bytes} and {self.options.max_block_size_bytes}"
            )

    def _validate_save_codecs(self, request: DownloadRequest) -> None:
        if (
            self.options.allowed_video_save_codecs is not None
            and request.stream.video_save_codec not in self.options.allowed_video_save_codecs
        ):
            raise ServerPolicyError(f"unsupported video save codec: {request.stream.video_save_codec}")
        if (
            self.options.allowed_audio_save_codecs is not None
            and request.stream.audio_save_codec not in self.options.allowed_audio_save_codecs
        ):
            raise ServerPolicyError(f"unsupported audio save codec: {request.stream.audio_save_codec}")

    @staticmethod
    def _validate_worker_count(field: str, value: int, maximum: int) -> None:
        if value < 1 or value > maximum:
            raise ServerPolicyError(f"{field} must be between 1 and {maximum}")

    @staticmethod
    def _resolve_request_path(path: Path, *, root: Path, field: str) -> Path:
        # anchor 检查覆盖 Windows 上 is_absolute() 为 False 的盘符相对/根路径（如 "/x"、"C:x"）
        if path.is_absolute() or path.anchor:
            raise ServerPolicyError(f"{field} must be relative to its configured root")
        if ".." in path.parts:
            raise ServerPolicyError(f"{field} must not contain '..'")

        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ServerPolicyError(f"{field} escapes its configured root")
        return resolved

    @staticmethod
    def _validate_subpath_template(template: str) -> None:
        # Template variables are filename-sanitized by path_templates.py, while
        # literal separators intentionally remain available for subdirectories.
        # Therefore only the literal template can introduce a parent traversal.
        path = Path(template)
        if path.is_absolute() or path.anchor:
            raise ServerPolicyError("output.subpath_template must be relative")
        if ".." in path.parts:
            raise ServerPolicyError("output.subpath_template must not contain '..'")
        allowed_fields = {
            "auto",
            "title",
            "id",
            "aid",
            "bvid",
            "name",
            "username",
            "series_title",
            "pubdate",
            "download_date",
            "owner_uid",
            "owner_uname",
        }
        time_field_pattern = re.compile(r"\{(?:pubdate|download_date)@[^{}]{1,128}\}")
        template_for_validation = time_field_pattern.sub("{download_date}", template)
        try:
            parsed_fields = list(Formatter().parse(template_for_validation))
        except ValueError as error:
            raise ServerPolicyError("output.subpath_template is invalid") from error
        for _, field_name, format_spec, conversion in parsed_fields:
            if field_name is None:
                continue
            if field_name not in allowed_fields:
                raise ServerPolicyError(f"output.subpath_template contains unsupported field: {field_name}")
            if conversion not in {None, "s", "r", "a"}:
                raise ServerPolicyError("output.subpath_template contains an unsupported conversion")
            ServerPolicy._validate_format_spec(format_spec or "")

    @staticmethod
    def _validate_format_spec(format_spec: str) -> None:
        if not format_spec:
            return
        if len(format_spec) > 32 or "{" in format_spec or "}" in format_spec:
            raise ServerPolicyError("output.subpath_template format spec is too complex")
        if any(separator in format_spec for separator in ("/", "\\", "..")):
            raise ServerPolicyError("output.subpath_template format spec contains an unsafe fill")
        if len(format_spec) >= 2 and format_spec[1] in "<>=^" and format_spec[0] == ".":
            raise ServerPolicyError("output.subpath_template format spec contains an unsafe fill")
        if any(int(width) > 256 for width in re.findall(r"\d+", format_spec)):
            raise ServerPolicyError("output.subpath_template format width is too large")


def snapshot_to_json(snapshot: TaskSnapshot[PayloadT, ResultT]) -> dict[str, object]:
    """Convert a task snapshot into a credential-safe JSON object."""
    result = snapshot_summary_to_json(snapshot)
    if snapshot.error is not None:
        error: dict[str, JsonValue] = {
            "code": snapshot.error.code,
            "type": snapshot.error.type,
            "message": snapshot.error.message,
        }
        if snapshot.error.truncated:
            error["truncated"] = True
        result["error"] = error
    result["payload"] = _to_json_value(snapshot.payload)
    result["result"] = _to_json_value(snapshot.result)
    return result


def snapshot_summary_to_json(snapshot: TaskSnapshot[PayloadT, ResultT]) -> dict[str, object]:
    """Convert a task snapshot without retaining or expanding its payload."""
    error: dict[str, JsonValue] | None = None
    if snapshot.error is not None:
        error = {"code": snapshot.error.code, "type": snapshot.error.type}
        if snapshot.error.truncated:
            error["truncated"] = True
    return {
        "task_id": snapshot.task_id,
        "state": snapshot.state.value,
        "error": error,
        "created_at": snapshot.created_at.isoformat(),
        "started_at": snapshot.started_at.isoformat() if snapshot.started_at is not None else None,
        "finished_at": snapshot.finished_at.isoformat() if snapshot.finished_at is not None else None,
        "last_event_seq": snapshot.last_event_seq,
    }


def event_to_json(event: TaskEvent) -> dict[str, object]:
    """Convert a runtime event into a credential-safe JSON object."""
    return {
        "task_id": event.task_id,
        "seq": event.seq,
        "kind": event.kind,
        "state": event.state.value,
        "created_at": event.created_at.isoformat(),
        "data": _to_json_value(event.data),
    }


def replay_to_json(replay: EventReplay) -> dict[str, object]:
    """Convert a bounded event replay into a JSON object."""
    return {
        "task_id": replay.task_id,
        "after_seq": replay.after_seq,
        "events": [event_to_json(event) for event in replay.events],
        "truncated": replay.truncated,
    }


def _to_json_value(value: object) -> JsonValue:
    if isinstance(value, Enum):
        return _to_json_value(value.value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        # wire 上的路径统一使用正斜杠，避免协议输出随 server 所在平台变化
        return value.as_posix()
    if isinstance(value, BaseModel):
        # python mode 保留 Path 等原生类型，统一交由本函数的分支序列化
        return _to_json_value(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            json_key = str(key)
            if _is_credential_field(json_key):
                continue
            if json_key.casefold() == "proxy" and isinstance(item, str):
                result[json_key] = sanitize_proxy_url(item)
                continue
            result[json_key] = _to_json_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_json_value(item) for item in value]
    raise TypeError(f"value of type {type(value).__name__} is not JSON compatible")


def _is_credential_field(field: str) -> bool:
    normalized = field.casefold().replace("-", "_")
    return normalized in _CREDENTIAL_FIELDS or normalized.endswith(
        ("_api_key", "_cookie", "_credential", "_password", "_secret", "_token")
    )
