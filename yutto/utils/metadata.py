import os
from typing import TypedDict
from xml.dom.minidom import parseString

import dicttoxml  # type: ignore


class MetaData(TypedDict):
    title: str
    show_title: str
    plot: str
    thumb: str
    premiered: str
    dataadded: str
    source: str
    original_filename: str


def write_metadata(metadata: MetaData, video_path: str):
    video_path_no_ext = os.path.splitext(video_path)[0]
    metadata_path = video_path_no_ext + ".nfo"
    custom_root = "episodedetails"

    xml_content = dicttoxml.dicttoxml(metadata, custom_root=custom_root, attr_type=False)  # type: ignore
    dom = parseString(xml_content)  # type: ignore
    pretty_content = dom.toprettyxml()  # type: ignore
    with open(metadata_path, "w", encoding="utf-8") as f:  # type: ignore
        f.write(pretty_content)  # type: ignore
