import re
from typing import Final, Literal, NamedTuple, Optional, TypedDict, Union

CSI: Final[str] = "\x1b["


class RGBColor(NamedTuple):
    r: int
    g: int
    b: int


TextColor = Literal[
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
]

Color = Union[TextColor, RGBColor]
Style = Literal["reset", "bold", "italic", "underline", "defaultfg", "defaultbg"]

_no_color = False


class CodeMap(TypedDict):
    fore: dict[TextColor, int]
    back: dict[TextColor, int]
    style: dict[Style, int]


code_map: CodeMap = {
    "fore": {
        "black": 30,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "blue": 34,
        "magenta": 35,
        "cyan": 36,
        "white": 37,
        "bright_black": 90,
        "bright_red": 91,
        "bright_green": 92,
        "bright_yellow": 93,
        "bright_blue": 94,
        "bright_magenta": 95,
        "bright_cyan": 96,
        "bright_white": 97,
    },
    "back": {
        "black": 40,
        "red": 41,
        "green": 42,
        "yellow": 43,
        "blue": 44,
        "magenta": 45,
        "cyan": 46,
        "white": 47,
        "bright_black": 100,
        "bright_red": 101,
        "bright_green": 102,
        "bright_yellow": 103,
        "bright_blue": 104,
        "bright_magenta": 105,
        "bright_cyan": 106,
        "bright_white": 107,
    },
    "style": {
        "reset": 0,
        "bold": 1,
        "italic": 3,
        "underline": 4,
        "defaultfg": 39,
        "defaultbg": 49,
    },
}


def colored_string(
    string: str, fore: Optional[Color] = None, back: Optional[Color] = None, style: Optional[list[Style]] = None
) -> str:
    if _no_color:
        return string
    code_list: list[int] = []

    if fore is not None:
        if isinstance(fore, str):
            code_list += [code_map["fore"][fore]]
        else:
            code_list += [38, 2, *fore]
    if back is not None:
        if isinstance(back, str):
            code_list += [code_map["back"][back]]
        else:
            code_list += [48, 2, *back]
    if style is not None:
        for s in style:
            code_list += [code_map["style"][s]]

    return f"{CSI}{';'.join(map(str, code_list))}m{string}{CSI}0m"


def no_colored_string(string: str) -> str:
    """ 去除字符串中的颜色码 """
    regex_color = re.compile(r"\x1b\[(\d+;)*\d+m")
    string = regex_color.sub("", string)
    return string


def set_no_color():
    global _no_color
    _no_color = True
