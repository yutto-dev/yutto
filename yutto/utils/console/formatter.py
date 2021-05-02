import re
from typing import Literal
from urllib.parse import unquote

_count: int = 0


def size_format(size: float, ndigits: int = 2, baseUnitSize: Literal[1024, 1000] = 1024) -> str:
    """ 输入数据字节数，与保留小数位数，返回数据量字符串 """
    sign = "-" if size < 0 else ""
    size = abs(size)
    unit_list = (
        ["Bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB", "BiB"]
        if baseUnitSize == 1024
        else ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB", "BB"]
    )

    index = 0
    while index < len(unit_list) - 1:
        if size >= baseUnitSize ** (index + 1):
            index += 1
        else:
            break
    return "{}{:.{}f} {}".format(sign, size / baseUnitSize ** index, ndigits, unit_list[index])


def get_char_width(char: str) -> int:
    """ 计算单个字符的宽度 """
    # fmt: off
    widths = [
        (126, 1), (159, 0), (687, 1), (710, 0), (711, 1),
        (727, 0), (733, 1), (879, 0), (1154, 1), (1161, 0),
        (4347, 1), (4447, 2), (7467, 1), (7521, 0), (8369, 1),
        (8426, 0), (9000, 1), (9002, 2), (11021, 1), (12350, 2),
        (12351, 1), (12438, 2), (12442, 0), (19893, 2), (19967, 1),
        (55203, 2), (63743, 1), (64106, 2), (65039, 1), (65059, 0),
        (65131, 2), (65279, 1), (65376, 2), (65500, 1), (65510, 2),
        (120831, 1), (262141, 2), (1114109, 1),
    ]
    # fmt: on

    o = ord(char)
    if o == 0xE or o == 0xF:
        return 0
    for num, wid in widths:
        if o <= num:
            return wid
    return 1


def get_string_width(string: str) -> int:
    """ 计算包含中文的字符串宽度 """
    # 去除颜色码
    string = no_color_string(string)
    try:
        length = sum([get_char_width(c) for c in string])
    except:
        length = len(string)
    return length


def no_color_string(string: str) -> str:
    """ 去除字符串中的颜色码 """
    regex_color = re.compile(r"\033\[\d+m")
    string = regex_color.sub("", string)
    return string


def repair_filename(filename: str) -> str:
    """ 修复不合法的文件名 """

    def to_full_width_chr(matchobj: "re.Match[str]") -> str:
        char = matchobj.group(0)
        full_width_char = chr(ord(char) + ord("？") - ord("?"))
        return full_width_char

    # 路径非法字符，转全角
    regex_path = re.compile(r'[\\/:*?"<>|]')
    # 空格类字符，转空格
    regex_spaces = re.compile(r"\s+")
    # 不可打印字符，移除
    regex_non_printable = re.compile(
        r"[\001\002\003\004\005\006\007\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        r"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a]"
    )

    # url decode
    filename = unquote(filename)
    filename = regex_path.sub(to_full_width_chr, filename)
    filename = regex_spaces.sub(" ", filename)
    filename = regex_non_printable.sub("", filename)
    filename = filename.strip()
    if not filename:
        filename = "未命名文件_{:04}".format(_count)
        _count += 1
    return filename
