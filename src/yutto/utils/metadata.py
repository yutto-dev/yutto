from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from dict2xml import dict2xml  # type: ignore

from yutto.utils.time import get_time_str_by_stamp

if TYPE_CHECKING:
    from pathlib import Path


class Actor(TypedDict):
    name: str
    role: str
    thumb: str
    profile: str
    order: int


class ChapterInfoData(TypedDict):
    start: int
    end: int
    content: str


class MetaData(TypedDict):
    title: str
    show_title: str
    plot: str
    thumb: str
    premiered: int
    dateadded: int
    actor: list[Actor]
    genre: list[str]
    tag: list[str]
    source: str
    original_filename: str
    website: str
    chapter_info_data: list[ChapterInfoData]


def metadata_value_format(metadata: MetaData, metadata_format: dict[str, str]) -> dict[str, Any]:
    formatted_metadata: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in metadata_format:
            assert isinstance(value, int)
            value = get_time_str_by_stamp(value, metadata_format[key])
        formatted_metadata[key] = value
    return formatted_metadata


def write_metadata(metadata: MetaData, video_path: Path, metadata_format: dict[str, str]):
    metadata_path = video_path.with_suffix(".nfo")
    custom_root = "episodedetails"  # TODO: 不同视频类型使用不同的 root name
    # 增加字段格式化内容，后续如果需要调整可以继续调整
    user_formatted_metadata = metadata_value_format(metadata, metadata_format) if metadata_format else metadata
    xml_content = dict2xml(user_formatted_metadata, wrap=custom_root, indent="  ")  # type: ignore
    with metadata_path.open("w", encoding="utf-8") as f:  # type: ignore
        f.write(xml_content)  # type: ignore


def attach_chapter_info(metadata: MetaData, chapter_info_data: list[ChapterInfoData]):
    metadata["chapter_info_data"] = chapter_info_data


# https://wklchris.github.io/blog/FFmpeg/FFmpeg.html#id26
def write_chapter_info(title: str, chapter_info_data: list[ChapterInfoData], chapter_path: Path):
    with chapter_path.open("w", encoding="utf-8") as f:
        f.write(";FFMETADATA1\n")
        f.write(f"title={title}\n")
        for chapter in chapter_info_data:
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1\n")
            f.write(f"START={chapter['start']}\n")
            f.write(f"END={chapter['end']}\n")
            f.write(f"title={chapter['content']}\n")
