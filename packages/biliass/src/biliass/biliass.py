# pyright: basic

from __future__ import annotations

import logging
import random
import re
from typing import TYPE_CHECKING, TypeVar

from biliass._core import (
    Comment,
    CommentPosition,
    Rows,
    ass_escape,
    convert_color,
    convert_flash_rotation,
    convert_timestamp,
    get_zoom_factor,
    parse_special_comment,
    read_comments_from_protobuf,
    read_comments_from_xml,
    write_comment_with_animation,
    write_head,
    write_normal_comment,
)

if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")


def read_comments_bilibili_xml(text: str | bytes, fontsize: float) -> list[Comment]:
    if isinstance(text, bytes):
        text = text.decode()
    return read_comments_from_xml(text, fontsize)


def read_comments_bilibili_protobuf(protobuf: bytes | str, fontsize: float) -> list[Comment]:
    assert isinstance(protobuf, bytes), "protobuf supports bytes only"
    return read_comments_from_protobuf(protobuf, fontsize)


BILI_PLACYER_SIZE = (891, 589)


class AssText:
    def __init__(self):
        self._text = ""

    def write_comment_special(self, comment: Comment, width, height, styleid):
        zoom_factor = get_zoom_factor(BILI_PLACYER_SIZE, (width, height))
        try:
            (
                (rotate_y, rotate_z, from_x, from_y, to_x, to_y),
                from_alpha,
                to_alpha,
                text,
                delay,
                lifetime,
                duration,
                fontface,
                is_border,
            ) = parse_special_comment(comment.comment, zoom_factor)

            self.write_comment_with_animation(
                comment,
                width,
                height,
                rotate_y,
                rotate_z,
                from_x,
                from_y,
                to_x,
                to_y,
                from_alpha,
                to_alpha,
                text,
                delay,
                lifetime,
                duration,
                fontface,
                is_border,
                styleid,
                zoom_factor,
            )

        except ValueError:
            logging.warning(f"Invalid comment: {comment.comment!r}")

    def write_head(self, width: int, height: int, fontface: str, fontsize: float, alpha: float, styleid: str) -> None:
        self._text += write_head(width, height, fontface, fontsize, alpha, styleid)

    def write_normal_comment(
        self,
        rows: Rows,
        comment: Comment,
        width: int,
        height: int,
        bottom_reserved: int,
        fontsize: float,
        duration_marquee: float,
        duration_still: float,
        styleid: str,
        reduced: bool,
    ) -> None:
        self._text += write_normal_comment(
            rows,
            comment,
            width,
            height,
            bottom_reserved,
            fontsize,
            duration_marquee,
            duration_still,
            styleid,
            reduced,
        )

    def write_comment_with_animation(
        self,
        comment: Comment,
        width: int,
        height: int,
        rotate_y: float,
        rotate_z: float,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        from_alpha: int,
        to_alpha: int,
        text: str,
        delay: float,
        lifetime: float,
        duration: float,
        fontface: str,
        is_border: bool,
        styleid: str,
        zoom_factor: tuple[float, float, float],
    ) -> None:
        self._text += write_comment_with_animation(
            comment,
            width,
            height,
            rotate_y,
            rotate_z,
            from_x,
            from_y,
            to_x,
            to_y,
            from_alpha,
            to_alpha,
            text,
            delay,
            lifetime,
            duration,
            fontface,
            is_border,
            styleid,
            zoom_factor,
        )

    def to_string(self):
        return self._text


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
    filters_regex,
    reduced: bool,
    progress_callback,
):
    styleid = f"biliass_{random.randint(0, 0xFFFF):04x}"
    ass = AssText()
    ass.write_head(width, height, fontface, fontsize, alpha, styleid)
    rows = Rows(4, height - bottom_reserved + 1)
    for idx, comment in enumerate(comments):
        if progress_callback and idx % 1000 == 0:
            progress_callback(idx, len(comments))
        if comment.pos in (
            CommentPosition.Scroll,
            CommentPosition.Bottom,
            CommentPosition.Top,
            CommentPosition.Reversed,
        ):
            skip = False
            for filter_regex in filters_regex:
                if filter_regex and filter_regex.search(comment.comment):
                    skip = True
                    break
            if skip:
                continue
            ass.write_normal_comment(
                rows,
                comment,
                width,
                height,
                bottom_reserved,
                fontsize,
                duration_marquee,
                duration_still,
                styleid,
                reduced,
            )
        elif comment.pos == CommentPosition.Special:
            ass.write_comment_special(comment, width, height, styleid)
        else:
            logging.warning(f"Invalid comment: {comment.comment!r}")
    if progress_callback:
        progress_callback(len(comments), len(comments))
    return ass.to_string()


class safe_list(list):
    def get(self, index, default=None):
        def is_empty(value):
            return value is None or value == ""

        try:
            return self[index] if not is_empty(self[index]) else default
        except IndexError:
            return default


def wrap_default(value: T | None, default: T) -> T:
    return default if value is None else value


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
    progress_callback: Callable[..., None] | None = None,
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
        progress_callback,
    )
