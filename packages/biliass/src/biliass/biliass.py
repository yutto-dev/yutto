from __future__ import annotations

from typing import TypeVar, cast

from biliass._core import (
    Comment,
    protobuf_to_ass,
    read_comments_from_protobuf,
    read_comments_from_xml,
    xml_to_ass,
)

T = TypeVar("T")


def read_comments_bilibili_xml(text: str | bytes, fontsize: float) -> list[Comment]:
    if isinstance(text, bytes):
        text = text.decode()
    return read_comments_from_xml(text, fontsize)


def read_comments_bilibili_protobuf(protobuf: bytes | str, fontsize: float) -> list[Comment]:
    assert isinstance(protobuf, bytes), "protobuf supports bytes only"
    return read_comments_from_protobuf(protobuf, fontsize)


def Danmaku2ASS(
    inputs: list[str | bytes] | str | bytes,
    stage_width: int,
    stage_height: int,
    input_format: str = "xml",
    reserve_blank: int = 0,
    font_face: str = "sans-serif",
    font_size: float = 25.0,
    text_opacity: float = 1.0,
    duration_marquee: float = 5.0,
    duration_still: float = 5.0,
    comment_filter: str | None = None,
    is_reduce_comments: bool = False,
) -> str:
    comment_filters: list[str] = [comment_filter] if comment_filter is not None else []
    if not isinstance(inputs, list):
        inputs = [inputs]

    if input_format == "xml":
        inputs = [text if isinstance(text, str) else text.decode() for text in inputs]
        return xml_to_ass(
            cast(list[str], inputs),
            stage_width,
            stage_height,
            reserve_blank,
            font_face,
            font_size,
            text_opacity,
            duration_marquee,
            duration_still,
            comment_filters,
            is_reduce_comments,
        )
    elif input_format == "protobuf":
        for input in inputs:
            if isinstance(input, str):
                raise ValueError("Protobuf can only be read from bytes")
        return protobuf_to_ass(
            cast(list[bytes], inputs),
            stage_width,
            stage_height,
            reserve_blank,
            font_face,
            font_size,
            text_opacity,
            duration_marquee,
            duration_still,
            comment_filters,
            is_reduce_comments,
        )
    else:
        raise TypeError(f"Invalid input format {input_format}")
