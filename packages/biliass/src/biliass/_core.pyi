from typing import Any

class ConversionOptions:
    def __init__(
        self,
        stage_width: int,
        stage_height: int,
        reserve_blank: int,
        font_face: str,
        font_size: float,
        text_opacity: float,
        duration_marquee: float,
        duration_still: float,
        is_reduce_comments: bool,
    ): ...

class BlockOptions:
    def __init__(
        self,
        block_top: bool,
        block_bottom: bool,
        block_scroll: bool,
        block_reverse: bool,
        block_special: bool,
        block_colorful: bool,
        block_keyword_patterns: list[str],
    ): ...
    def default() -> BlockOptions: ...

def xml_to_ass(
    inputs: list[str],
    conversion_options: ConversionOptions,
    block_options: dict[str, Any],
    is_reduce_comments: bool,
) -> str: ...
def protobuf_to_ass(
    inputs: list[bytes],
    conversion_options: ConversionOptions,
    block_options: dict[str, Any],
    is_reduce_comments: bool,
) -> str: ...
def get_danmaku_meta_size(buffer: bytes) -> int: ...
def enable_tracing() -> None: ...
