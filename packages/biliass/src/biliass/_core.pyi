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
def convert_timestamp(timestamp: float) -> float: ...
def ass_escape(text: str) -> str: ...
def convert_color(rgb: int, width: int = ..., height: int = ...) -> str: ...
def get_zoom_factor(source_size: tuple[int, int], target_size: tuple[int, int]) -> tuple[float, float, float]: ...
def convert_flash_rotation(
    rot_y: float, rot_z: float, x: float, y: float, width: float, height: float
) -> tuple[float, float, float, float, float, float, float]: ...

class Rows:
    def __init__(self, num_types: int, capacity: int) -> None: ...

def write_head(width: int, height: int, fontface: str, fontsize: float, alpha: float, styleid: str) -> str: ...
def write_normal_comment(
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
) -> str: ...
def write_comment_with_animation(
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
) -> str: ...
