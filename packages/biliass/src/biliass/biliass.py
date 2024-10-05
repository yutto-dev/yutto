from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, TypeVar, cast

from biliass._core import (
    protobuf_to_ass,
    xml_to_ass,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

T = TypeVar("T")


class BlockOptions(TypedDict):
    block_top: bool
    block_bottom: bool
    block_scroll: bool
    block_reverse: bool
    block_special: bool
    block_colorful: bool
    block_keyword_patterns: list[str]


def create_default_block_options() -> BlockOptions:
    return BlockOptions(
        block_top=False,
        block_bottom=False,
        block_scroll=False,
        block_reverse=False,
        block_special=False,
        block_colorful=False,
        block_keyword_patterns=[],
    )


def Danmaku2ASS(
    inputs: Sequence[str | bytes] | str | bytes,
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
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    print("Function `Danmaku2ASS` is deprecated in biliass 2.0.0, Please use `convert_to_ass` instead.")
    if progress_callback is not None:
        print("`progress_callback` is deprecated in 2.0.0 and will be removed in 2.1.0")
    comment_filters: list[str] = [comment_filter] if comment_filter is not None else []
    # block_options = BlockOptions(False, False, False, False, False, False, comment_filters)
    block_options = BlockOptions(
        block_top=False,
        block_bottom=False,
        block_scroll=False,
        block_reverse=False,
        block_special=False,
        block_colorful=False,
        block_keyword_patterns=comment_filters,
    )
    return convert_to_ass(
        inputs,
        stage_width,
        stage_height,
        input_format,
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        block_options,
        is_reduce_comments,
    )


def convert_to_ass(
    inputs: Sequence[str | bytes] | str | bytes,
    stage_width: int,
    stage_height: int,
    input_format: str = "xml",
    reserve_blank: int = 0,
    font_face: str = "sans-serif",
    font_size: float = 25.0,
    text_opacity: float = 1.0,
    duration_marquee: float = 5.0,
    duration_still: float = 5.0,
    block_options: BlockOptions | None = None,
    is_reduce_comments: bool = False,
) -> str:
    block_options = block_options or create_default_block_options()
    if isinstance(inputs, (str, bytes)):
        inputs = [inputs]

    if input_format == "xml":
        inputs = [text if isinstance(text, str) else text.decode() for text in inputs]
        return xml_to_ass(
            inputs,
            stage_width,
            stage_height,
            reserve_blank,
            font_face,
            font_size,
            text_opacity,
            duration_marquee,
            duration_still,
            # block_options,
            block_options["block_top"],
            # block_options["block_bottom"],
            # block_options["block_scroll"],
            # block_options["block_reverse"],
            # block_options["block_special"],
            # block_options["block_colorful"],
            # block_options["block_keyword_patterns"],
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
            # block_options,
            block_options["block_top"],
            # block_options["block_bottom"],
            # block_options["block_scroll"],
            # block_options["block_reverse"],
            # block_options["block_special"],
            # block_options["block_colorful"],
            # block_options["block_keyword_patterns"],
            is_reduce_comments,
        )
    else:
        raise TypeError(f"Invalid input format {input_format}")
