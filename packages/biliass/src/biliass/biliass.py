from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

from biliass._core import (
    BlockOptions,
    ConversionOptions,
    protobuf_to_ass,
    xml_to_ass,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

T = TypeVar("T")


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
    print(
        "Function `Danmaku2ASS` is deprecated in biliass 2.0.0 and will be removed in 2.2.0, Please use `convert_to_ass` instead."
    )
    if progress_callback is not None:
        print("`progress_callback` will take no effect in 2.0.0")
    comment_filters: list[str] = [comment_filter] if comment_filter is not None else []
    block_options = BlockOptions(False, False, False, False, False, False, comment_filters)
    return convert_to_ass(
        inputs,
        stage_width,
        stage_height,
        input_format,
        1 - reserve_blank / stage_height,
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
    display_region_ratio: float = 1.0,
    font_face: str = "sans-serif",
    font_size: float = 25.0,
    text_opacity: float = 1.0,
    duration_marquee: float = 5.0,
    duration_still: float = 5.0,
    block_options: BlockOptions | None = None,
    reduce_comments: bool = True,
) -> str:
    if isinstance(inputs, (str, bytes)):
        inputs = [inputs]
    conversion_options = ConversionOptions(
        stage_width,
        stage_height,
        display_region_ratio,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        reduce_comments,
    )
    block_options = block_options or BlockOptions.default()

    if input_format == "xml":
        inputs = [text if isinstance(text, str) else text.decode() for text in inputs]
        return xml_to_ass(
            inputs,
            conversion_options,
            block_options,
        )
    elif input_format == "protobuf":
        for input in inputs:
            if isinstance(input, str):
                raise ValueError("Protobuf can only be read from bytes")
        return protobuf_to_ass(
            cast(list[bytes], inputs),
            conversion_options,
            block_options,
        )
    else:
        raise TypeError(f"Invalid input format {input_format}")
