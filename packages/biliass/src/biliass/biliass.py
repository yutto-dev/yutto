# pyright: basic

from __future__ import annotations

import logging
import random
import re
from typing import TypeVar

from biliass._core import (
    Comment,
    process_comments as process_comments_rs,
    read_comments_from_protobuf,
    read_comments_from_xml,
)

T = TypeVar("T")


def read_comments_bilibili_xml(text: str | bytes, fontsize: float) -> list[Comment]:
    if isinstance(text, bytes):
        text = text.decode()
    return read_comments_from_xml(text, fontsize)


def read_comments_bilibili_protobuf(protobuf: bytes | str, fontsize: float) -> list[Comment]:
    assert isinstance(protobuf, bytes), "protobuf supports bytes only"
    return read_comments_from_protobuf(protobuf, fontsize)


def process_comments(
    comments: list[Comment],
    width: int,
    height: int,
    bottom_reserved: int,
    fontface: str,
    fontsize: float,
    alpha: float,
    duration_marquee: float,
    duration_still: float,
    filters_regex: list[re.Pattern[str]],
    reduced: bool,
):
    styleid = f"biliass_{random.randint(0, 0xFFFF):04x}"
    return process_comments_rs(
        comments,
        width,
        height,
        styleid,
        bottom_reserved,
        fontface,
        fontsize,
        alpha,
        duration_marquee,
        duration_still,
        [filter_regex.pattern for filter_regex in filters_regex],
        reduced,
    )


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
    filters_regex = []
    for comment_filter in comment_filters:
        try:
            if comment_filter:
                filters_regex.append(re.compile(comment_filter))
        except:  # noqa: E722
            raise ValueError(f"Invalid regular expression: {comment_filter}") from None

    comments: list[Comment] = []
    if not isinstance(inputs, list):
        inputs = [inputs]
    for input in inputs:
        if input_format == "xml":
            comments.extend(read_comments_bilibili_xml(input, font_size))
        else:
            if isinstance(input, str):
                logging.warning("Protobuf can only be read from bytes")
            comments.extend(read_comments_bilibili_protobuf(input, font_size))
    comments.sort(
        key=lambda comment: (
            comment.timeline,
            comment.timestamp,
            comment.no,
            comment.comment,
            comment.pos,
            comment.color,
            comment.size,
            comment.height,
            comment.width,
        )
    )
    return process_comments(
        comments,
        stage_width,
        stage_height,
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        filters_regex,
        is_reduce_comments,
    )
