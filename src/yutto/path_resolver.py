from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from typing import Literal

from yutto.utils.console.logger import Logger
from yutto.utils.time import get_time_str_by_stamp

PathTemplateVariable = Literal[
    "title", "id", "aid", "bvid", "name", "username", "series_title", "pubdate", "download_date", "owner_uid"
]
PathTemplateVariableDict = dict[PathTemplateVariable, int | str]
UNKNOWN: str = "unknown_variable"

_count: int = 0


def repair_filename(filename: str) -> str:
    """修复不合法的文件名"""

    global _count

    def to_full_width_chr(matchobj: re.Match[str]) -> str:
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
    # 尾部多个 .，转为省略号
    regex_dots = re.compile(r"\.+$")

    # 由于部分内容可能是从 HTML 解析的，所以使用 html 反转义
    filename = unescape(filename)
    filename = regex_path.sub(to_full_width_chr, filename)
    filename = regex_spaces.sub(" ", filename)
    filename = regex_non_printable.sub("", filename)
    filename = filename.strip()
    filename = regex_dots.sub("……", filename)
    if not filename:
        filename = f"未命名文件_{_count:04}"
        _count += 1
    return filename


def create_time_formatter(name: str, value: int):
    regex = re.compile(rf"{{{name}(@(?P<timefmt>.+?))?}}")
    DEFAULT_TIMEFMT = "%Y-%m-%d"

    def convert_pubdate(matchobj: re.Match[str]):
        timefmt = matchobj.group("timefmt")
        if timefmt is None:
            timefmt = DEFAULT_TIMEFMT
        formatted_time = repair_filename(get_time_str_by_stamp(value, timefmt))
        return formatted_time

    def formatter(text: str):
        return regex.sub(convert_pubdate, text)

    return formatter


def resolve_path_template(
    path_template: str, auto_path_template: str, subpath_variables: PathTemplateVariableDict
) -> str:
    # 保证所有传进来的值都满足路径要求
    for key, value in subpath_variables.items():
        # 未知变量警告
        if f"{{{key}}}" in path_template and value == UNKNOWN:
            Logger.warning("使用了未知的变量，可能导致产生错误的下载路径")
        # 只对字符串值修改，int 型不修改以适配高级模板
        if isinstance(value, str):
            subpath_variables[key] = repair_filename(value)

    # 将时间变量转换为对应的时间格式
    time_vars: list[PathTemplateVariable] = ["pubdate", "download_date"]
    for var in time_vars:
        value = subpath_variables.pop(var)
        if value == UNKNOWN:
            continue
        assert isinstance(value, int), f"变量 {var} 的值必须为 int 型，但是传入了 {value}"
        time_formatter = create_time_formatter(var, value)
        path_template = time_formatter(path_template)
    return path_template.format(auto=auto_path_template.format(**subpath_variables), **subpath_variables)


def create_unique_path_resolver():
    """确保同一次下载不会存在相同的路径
    如分 P 命名完全相同（BV1Ua4y1W7cq）
    """
    seen_path_count: dict[str, int] = {}

    def unique_path(path_str: str) -> str:
        """确保路径唯一"""
        seen_path_count.setdefault(path_str, -1)
        seen_path_count[path_str] += 1
        if seen_path_count[path_str] == 0:
            return path_str
        path = Path(path_str)
        return str(path.parent / f"{path.stem} ({seen_path_count[path_str]}){path.suffix}")

    return unique_path
