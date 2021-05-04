import os
from typing import Literal, Optional

from biliass import Danmaku2ASS

DanmakuType = Literal["xml", "ass", "no"]


def write_xml_danmaku(xml_danmaku: str, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(xml_danmaku)


def write_ass_danmaku(xml_danmaku: str, filepath: str, height: int, width: int):
    with open(
        filepath,
        "w",
        encoding="utf-8-sig",
        errors="replace",
    ) as f:
        f.write(
            Danmaku2ASS(
                xml_danmaku,
                height,
                width,
                reserve_blank=0,
                font_face="sans-serif",
                font_size=width / 40,
                text_opacity=0.8,
                duration_marquee=15.0,
                duration_still=10.0,
                comment_filter=None,
                is_reduce_comments=False,
                progress_callback=None,
            )
        )


def write_danmaku(
    xml_danmaku: str, video_path: str, height: int, width: int, danmaku_type: DanmakuType
) -> Optional[str]:
    video_path_no_ext = os.path.splitext(video_path)[0]
    if danmaku_type == "xml":
        file_path = video_path_no_ext + ".xml"
        write_xml_danmaku(xml_danmaku, file_path)
    elif danmaku_type == "ass":
        file_path = video_path_no_ext + ".ass"
        write_ass_danmaku(xml_danmaku, file_path, height, width)
    else:
        return None
