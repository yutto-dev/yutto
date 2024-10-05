class ConversionOptions:
    def __init__(
        self,
        stage_width: int,
        stage_height: int,
        display_region_ratio: float,
        font_face: str,
        font_size: float,
        text_opacity: float,
        duration_marquee: float,
        duration_still: float,
        is_reduce_comments: bool,
    ) -> None: ...

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
    ) -> None: ...
    @staticmethod
    def default() -> BlockOptions: ...

def xml_to_ass(
    inputs: list[str],
    conversion_options: ConversionOptions,
    block_options: BlockOptions,
) -> str: ...
def protobuf_to_ass(
    inputs: list[bytes],
    conversion_options: ConversionOptions,
    block_options: BlockOptions,
) -> str: ...
def get_danmaku_meta_size(buffer: bytes) -> int: ...
def enable_tracing() -> None: ...
