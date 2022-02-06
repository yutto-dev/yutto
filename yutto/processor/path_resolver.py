import re
from html import unescape
from typing import Literal, Union

from yutto.utils.console.logger import Logger

path_template_variables = ["title", "id", "name", "username"]
PathTemplateVariable = Literal["title", "id", "name", "username", "series_title", "pubdate"]
PathTemplateVariableDict = dict[PathTemplateVariable, Union[int, str]]
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


def resolve_path_template(
    path_template: str, auto_path_template: str, subpath_variables: PathTemplateVariableDict
) -> str:
    # fav_title 已经被 series_title 取代
    if "{fav_title}" in path_template:
        Logger.deprecated_warning("路径变量 fav_title 已经被废除，已自动使用 series_title 替代（2.0.0 后将会彻底废除 fav_title）")
        path_template = path_template.replace("{fav_title}", "{series_title}")
    # 保证所有传进来的值都满足路径要求
    for key, value in subpath_variables.items():
        # 只对字符串值修改，int 型不修改以适配高级模板
        if isinstance(value, str):
            if f"{{{key}}}" in path_template and value == UNKNOWN:
                Logger.warning("使用了未知的变量，可能导致产生错误的下载路径")
            subpath_variables[key] = repair_filename(value)
    return path_template.format(auto=auto_path_template.format(**subpath_variables), **subpath_variables)
