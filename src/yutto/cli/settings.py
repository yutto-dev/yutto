from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from yutto.media.quality import (
    AudioQuality,
    VideoQuality,
)
from yutto.utils.console.logger import Logger
from yutto.utils.time import TIME_DATE_FMT

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def xdg_config_home() -> Path:
    if (env := os.environ.get("XDG_CONFIG_HOME")) and (path := Path(env)).is_absolute():
        return path
    home = Path.home()
    if platform.system() == "Windows":
        return home / "AppData" / "Roaming"
    return home / ".config"


class YuttoBasicSettings(BaseModel):
    num_workers: Annotated[int, Field(8, gt=0)]
    video_quality: Annotated[VideoQuality, Field(127)]
    audio_quality: Annotated[AudioQuality, Field(30251)]
    vcodec: Annotated[str, Field("avc:copy")]
    acodec: Annotated[str, Field("mp4a:copy")]
    download_vcodec_priority: Annotated[list[str] | None, Field(None)]
    output_format: Annotated[Literal["infer", "mp4", "mkv", "mov"], Field("infer")]
    output_format_audio_only: Annotated[
        Literal["infer", "m4a", "aac", "mp3", "flac", "mp4", "mkv", "mov"], Field("infer")
    ]
    ai_translation_language: Annotated[str | None, Field(None)]
    danmaku_format: Annotated[Literal["xml", "ass", "protobuf"], Field("ass")]
    block_size: Annotated[float, Field(0.5)]
    overwrite: Annotated[bool, Field(False)]
    proxy: Annotated[str, Field("auto")]
    dir: Annotated[str, Field("./")]
    tmp_dir: Annotated[str | None, Field(None)]
    sessdata: Annotated[str, Field("")]  # legacy 兼容字段，推荐使用 [auth].auth
    subpath_template: Annotated[str, Field("{auto}")]
    aliases: Annotated[dict[str, str], Field(dict[str, str]())]
    metadata_format_premiered: Annotated[str, Field(TIME_DATE_FMT)]
    download_interval: Annotated[int, Field(0)]
    banned_mirrors_pattern: Annotated[str | None, Field(None)]
    vip_strict: Annotated[bool, Field(False)]
    login_strict: Annotated[bool, Field(False)]
    no_color: Annotated[bool, Field(False)]
    no_progress: Annotated[bool, Field(False)]
    debug: Annotated[bool, Field(False)]


class YuttoResourceSettings(BaseModel):
    require_video: Annotated[bool, Field(True)]
    require_audio: Annotated[bool, Field(True)]
    require_danmaku: Annotated[bool, Field(True)]
    require_subtitle: Annotated[bool, Field(True)]
    require_metadata: Annotated[bool, Field(False)]
    require_cover: Annotated[bool, Field(True)]
    require_chapter_info: Annotated[bool, Field(True)]
    save_cover: Annotated[bool, Field(False)]


class YuttoDanmakuSettings(BaseModel):
    font_size: Annotated[int | None, Field(None)]
    font: Annotated[str, Field("SimHei")]
    opacity: Annotated[float, Field(0.8)]
    display_region_ratio: Annotated[float, Field(1.0)]
    speed: Annotated[float, Field(1.0)]
    block_top: Annotated[bool, Field(False)]
    block_bottom: Annotated[bool, Field(False)]
    block_scroll: Annotated[bool, Field(False)]
    block_reverse: Annotated[bool, Field(False)]
    block_fixed: Annotated[bool, Field(False)]
    block_special: Annotated[bool, Field(False)]
    block_colorful: Annotated[bool, Field(False)]
    block_keyword_patterns: Annotated[list[str], Field(list[str]())]


class YuttoBatchSettings(BaseModel):
    with_section: Annotated[bool, Field(False)]
    batch_filter_start_time: Annotated[str | None, Field(None)]
    batch_filter_end_time: Annotated[str | None, Field(None)]


class YuttoAuthSettings(BaseModel):
    auth: Annotated[str, Field("")]
    auth_file: Annotated[str | None, Field(None)]
    auth_profile: Annotated[str, Field("default")]


class YuttoSettings(BaseModel):
    basic: Annotated[YuttoBasicSettings, Field(YuttoBasicSettings())]  # pyright: ignore[reportCallIssue]
    resource: Annotated[YuttoResourceSettings, Field(YuttoResourceSettings())]  # pyright: ignore[reportCallIssue]
    danmaku: Annotated[YuttoDanmakuSettings, Field(YuttoDanmakuSettings())]  # pyright: ignore[reportCallIssue]
    batch: Annotated[YuttoBatchSettings, Field(YuttoBatchSettings())]  # pyright: ignore[reportCallIssue]
    auth: Annotated[YuttoAuthSettings, Field(YuttoAuthSettings())]  # pyright: ignore[reportCallIssue]


def search_for_settings_file() -> Path | None:
    settings_file = Path("yutto.toml")
    # 此时还没有设置 debug，所以 Logger.debug 永远不会输出
    if not settings_file.exists():
        Logger.debug("Settings file not found in current directory.")
        settings_file = xdg_config_home() / "yutto" / "yutto.toml"
    if not settings_file.exists():
        Logger.debug(f"Settings file not found in XDG_CONFIG_HOME ({settings_file}).")
        return None
    Logger.debug(f"Settings file found at {settings_file}.")
    return settings_file


def load_settings_file(settings_file: Path) -> YuttoSettings:
    with settings_file.open("r", encoding="utf-8") as f:
        settings_raw: Any = tomllib.loads(f.read())  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return YuttoSettings.model_validate(settings_raw)


if __name__ == "__main__":
    settings_file = search_for_settings_file()
    assert settings_file is not None
    settings = load_settings_file(settings_file)
    print(settings.model_dump())
