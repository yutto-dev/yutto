from __future__ import annotations

import time
from pathlib import Path
from typing import TypedDict

from dict2xml import dict2xml  # type: ignore


class Actor(TypedDict):
    name: str
    role: str
    thumb: str
    profile: str
    order: int


class MetaData(TypedDict):
    title: str
    show_title: str
    plot: str
    thumb: str
    premiered: time.struct_time
    dateadded: str
    actor: list[Actor]
    genre: list[str]
    tag: list[str]
    source: str
    original_filename: str
    website: str


def metadata_value_format(metadata: MetaData, metadata_format: dict[str, str | None]) -> TypedDict:
    for key, fmt in metadata_format.items():
        if fmt and key in metadata:
            # datetime
            if isinstance(metadata[key], (time.struct_time)):  # TODO: datetime.datetime
                metadata[key]: str = time.strftime(fmt, metadata[key])  # type: ignore
    return metadata


def write_metadata(metadata: MetaData, video_path: Path, metadata_format: dict[str, str | None]):
    metadata_path = video_path.with_suffix(".nfo")
    custom_root = "episodedetails"  # TODO: 不同视频类型使用不同的root name
    # 增加字段格式化内容，后续如果需要调整可以继续调整
    user_formatted_metadata: TypedDict = (
        metadata_value_format(metadata, metadata_format) if metadata_format else metadata
    )
    xml_content = dict2xml(user_formatted_metadata, wrap=custom_root, indent="  ")  # type: ignore
    with metadata_path.open("w", encoding="utf-8") as f:  # type: ignore
        f.write(xml_content)  # type: ignore
