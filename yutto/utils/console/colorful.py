from typing import Literal, Optional, TypedDict

Fore = Literal["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
Back = Literal["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
Style = Literal["reset", "bold", "italic", "underline", "defaultfg", "defaultbg"]

_no_color = False


class CodeMap(TypedDict):
    fore: dict[Fore, int]
    back: dict[Back, int]
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
    string: str, fore: Optional[Fore] = None, back: Optional[Back] = None, style: Optional[Style] = None
) -> str:
    if _no_color:
        return string
    template = "\033[{code}m"
    result = ""
    if fore is not None:
        result += template.format(code=code_map["fore"][fore])
    if back is not None:
        result += template.format(code=code_map["back"][back])
    if style is not None:
        result += template.format(code=code_map["style"][style])
    result += string
    result += template.format(code=code_map["style"]["reset"])
    return result


def set_no_color():
    global _no_color
    _no_color = True
