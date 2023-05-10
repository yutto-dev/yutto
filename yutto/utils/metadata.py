from __future__ import annotations

from pathlib import Path
from typing import TypedDict
from xml.dom.minidom import parseString  # type: ignore

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
    premiered: str
    dateadded: str
    actor: list[Actor]
    genre: list[str]
    tag: list[str]
    source: str
    original_filename: str
    website: str


def write_metadata(metadata: MetaData, video_path: Path):
    metadata_path = video_path.with_suffix(".nfo")
    custom_root = "episodedetails"  # TODO: 不同视频类型使用不同的root name
    xml_content = dict2xml(metadata, wrap=custom_root, indent="  ")  # type: ignore
    with metadata_path.open("w", encoding="utf-8") as f:  # type: ignore
        f.write(xml_content)  # type: ignore
