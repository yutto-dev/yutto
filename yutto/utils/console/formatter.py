from typing import Literal

from yutto.utils.console.colorful import no_colored_string


def size_format(size: float, ndigits: int = 2, base_unit_size: Literal[1024, 1000] = 1024) -> str:
    """ 输入数据字节数，与保留小数位数，返回数据量字符串 """
    sign = "-" if size < 0 else ""
    size = abs(size)
    unit_list = (
        ["Bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB", "BiB"]
        if base_unit_size == 1024
        else ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB", "BB"]
    )

    index = 0
    while index < len(unit_list) - 1:
        if size >= base_unit_size ** (index + 1):
            index += 1
        else:
            break
    return "{}{:.{}f} {}".format(sign, size / base_unit_size ** index, ndigits, unit_list[index])


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
    string = no_colored_string(string)
    try:
        length = sum([get_char_width(c) for c in string])
    except:
        length = len(string)
    return length
