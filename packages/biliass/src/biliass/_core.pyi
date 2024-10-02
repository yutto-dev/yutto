def xml_to_ass(
    inputs: list[str],
    stage_width: int,
    stage_height: int,
    reserve_blank: int,
    font_face: str,
    font_size: float,
    text_opacity: float,
    duration_marquee: float,
    duration_still: float,
    comment_filter: list[str],
    is_reduce_comments: bool,
) -> str: ...
def protobuf_to_ass(
    inputs: list[bytes],
    stage_width: int,
    stage_height: int,
    reserve_blank: int,
    font_face: str,
    font_size: float,
    text_opacity: float,
    duration_marquee: float,
    duration_still: float,
    comment_filter: list[str],
    is_reduce_comments: bool,
) -> str: ...
def get_danmaku_meta_size(buffer: bytes) -> int: ...
def enable_tracing() -> None: ...
