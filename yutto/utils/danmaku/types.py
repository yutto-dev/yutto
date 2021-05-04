from typing import TypedDict
from enum import Enum


class DanmakuMode(Enum):
    NORMAL1 = 1
    NORMAL2 = 2
    NORMAL3 = 3
    BOTTOM = 4
    TOP = 5
    REVERSED = 6
    SPECIAL1 = 7
    SPECIAL2 = 8
    SPECIAL3 = 9


class DanmakuData(TypedDict):
    content: str
    time: float
    mode: DanmakuMode
    font_size: int
    color: str
