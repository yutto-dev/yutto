from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

from biliass._core import (
    BlockOptions,
    ConversionOptions,
    protobuf_to_ass,
    xml_to_ass,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

T = TypeVar("T")


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
            cast("list[bytes]", inputs),
            conversion_options,
            block_options,
        )
    else:
        raise TypeError(f"Invalid input format {input_format}")
