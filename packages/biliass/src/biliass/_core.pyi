from typing import ClassVar

class DanmakuElem:
    @property
    def id(self) -> int: ...
    @property
    def progress(self) -> int: ...
    @property
    def mode(self) -> int: ...
    @property
    def fontsize(self) -> int: ...
    @property
    def color(self) -> int: ...
    @property
    def mid_hash(self) -> str: ...
    @property
    def content(self) -> str: ...
    @property
    def ctime(self) -> int: ...
    @property
    def action(self) -> str: ...
    @property
    def pool(self) -> int: ...
    @property
    def id_str(self) -> str: ...
    @property
    def attr(self) -> int: ...
    @property
    def animation(self) -> str: ...

class DmSegMobileReply:
    @property
    def elems(self) -> list[DanmakuElem]: ...
    @staticmethod
    def decode(data: bytes) -> DmSegMobileReply: ...

class CommentPosition:
    Scroll: ClassVar[CommentPosition]
    Top: ClassVar[CommentPosition]
    Bottom: ClassVar[CommentPosition]
    Reversed: ClassVar[CommentPosition]
    Special: ClassVar[CommentPosition]

    @property
    def id(self) -> int: ...

class Comment:
    timeline: float
    timestamp: int
    no: int
    comment: str
    pos: CommentPosition
    color: int
    size: float
    height: float
    width: float

def read_comments_from_xml(text: str, fontsize: float) -> list[Comment]: ...
def read_comments_from_protobuf(data: bytes, fontsize: float) -> list[Comment]: ...
def parse_special_comment(
    content: str, zoom_factor: tuple[float, float, float]
) -> tuple[tuple[int, int, float, float, float, float], int, int, str, int, float, int, str, bool]: ...
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
