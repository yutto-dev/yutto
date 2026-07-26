from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

from yutto.core.operation import emit_download_report
from yutto.exceptions import WrongArgumentError


def path_from_cli(path: str) -> Path:
    """从命令行参数获取路径，支持 ~，以便配置中使用 ~"""
    return Path(path).expanduser()


def is_comment(line: str) -> bool:
    """判断文件某行是否为注释"""
    if line.startswith("#"):
        return True
    return False


def alias_parser(file_path: str) -> dict[str, str]:
    result: dict[str, str] = {}
    re_alias_splitter = re.compile(r"[\s=]")
    with path_from_cli(file_path).open("r") as f_alias:
        for line in f_alias:
            line = line.strip()
            if not line or is_comment(line):
                continue
            alias, url = re_alias_splitter.split(line, maxsplit=1)
            result[alias] = url
    return result


def file_scheme_parser(url: str) -> list[str]:
    file_url: str = urllib.parse.urlparse(url).path
    file_path = path_from_cli(urllib.request.url2pathname(file_url))
    emit_download_report(f"解析下载列表 {file_path} 中...")
    result: list[str] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or is_comment(line):
                continue
            result.append(line)
    return result


def validate_episodes_selection(episodes_str: str) -> bool:
    regex_number = r"(-?(0|[1-9]\d*))"
    regex_episode = rf"({regex_number}|\$|\^)"
    regex_range = rf"({regex_episode}|({regex_episode}?~{regex_episode}?))"
    regex_compose = rf"{regex_range}(,{regex_range})*"
    return bool(re.match(rf"{regex_compose}$", episodes_str))


def validate_batch_selection(episodes: str) -> None:
    """检查 Core 请求中的批量选集格式。"""
    if not validate_episodes_selection(episodes):
        raise WrongArgumentError(f"选集参数（{episodes}）格式不正确呀～重新检查一下下～")


def parse_episodes_selection(episodes_str: str, total: int) -> list[int]:
    """将选集字符串转为列表（标号从 1 开始）"""

    if total == 0:
        emit_download_report(
            "该剧集列表无任何剧集，猜测正片尚未上线，如果想要下载 PV 等特殊剧集，请添加参数 -s",
            "warning",
        )
        return []

    def resolve_negative(value: int) -> int:
        if value == 0:
            raise WrongArgumentError("不可使用 0 作为剧集号（剧集号从 1 开始计算）")
        return value if value > 0 else value + total + 1

    # 解析字符串为列表
    emit_download_report(f"全 {total} 话")
    if validate_episodes_selection(episodes_str):
        episodes_str = episodes_str.replace("$", "-1")
        episode_list: list[int] = []
        for episode_item in episodes_str.split(","):
            if "~" in episode_item:
                split_range = episode_item.split("~")
                if len(split_range) != 2:
                    raise WrongArgumentError(f"{episode_item} 选集参数每部分至多包含一个 ~")
                start, end = split_range
                start, end = "1" if not start else start, "-1" if not end else end
                start, end = int(start), int(end)
                start, end = resolve_negative(start), resolve_negative(end)
                if not (end >= start):
                    raise WrongArgumentError(f"终点值（{end}）应不小于起点值（{start}）")
                episode_list.extend(list(range(start, end + 1)))
            else:
                episode_item = int(episode_item)
                episode_item = resolve_negative(episode_item)
                episode_list.append(episode_item)
    else:
        episode_list = []

    episode_list = sorted(set(episode_list))

    # 筛选满足条件的剧集
    out_of_range: list[int] = []
    episodes: list[int] = []
    for episode in episode_list:
        if episode in range(1, total + 1):
            if episode not in episodes:
                episodes.append(episode)
        else:
            out_of_range.append(episode)
    if out_of_range:
        emit_download_report("剧集 {} 不存在".format(",".join(list(map(str, out_of_range)))), "warning")

    emit_download_report("已选择第 {} 话".format(",".join(list(map(str, episodes)))))
    if not episodes:
        emit_download_report("没有选中任何剧集", "warning")
    return episodes
