from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from yutto.api.ugc_video import UgcVideoListItem
    from yutto.utils.metadata import MetaData

# 收藏夹路径模板：单分 p 视频直接以标题命名，多分 p 视频在标题目录下展开
FAVOURITE_SINGLE_PAGE_TEMPLATE = "{username}的收藏夹/{series_title}/{title}"
FAVOURITE_MULTI_PAGE_TEMPLATE = "{username}的收藏夹/{series_title}/{title}/{name}"


def normalize_favourite_video_item(
    ugc_video_item: UgcVideoListItem,
    favourite_title: str,
    *,
    is_single_page_video: bool,
) -> tuple[UgcVideoListItem, str, str | None]:
    """根据视频是否为单分 p，规范化收藏夹条目的文件名和路径模板。

    对于多分 p 视频：
    - 返回多分 p 路径模板，并将收藏夹人工标题作为分组名（display_group）。

    对于单分 p 视频：
    - 将 metadata 中的标题替换为 B 站侧的人工标题，解决机器生成文件名的问题。
    - 返回单分 p 路径模板，分组名为 None。

    Args:
        ugc_video_item: 从 get_ugc_video_list 获取的单个分 p 条目。
        favourite_title: 收藏夹 API 返回的视频标题（B 站人工填写）。
        is_single_page_video: 该视频是否只有一个分 p。

    Returns:
        (规范化后的条目, 路径模板字符串, display_group)
    """
    if not is_single_page_video:
        # 多分 p：以收藏夹标题作为分组展示，分 p 名保持与普通投稿视频一致
        return ugc_video_item, FAVOURITE_MULTI_PAGE_TEMPLATE, favourite_title

    # 单分 p：用 B 站侧人工标题覆盖 metadata，避免使用机器生成的文件名
    metadata = cast(
        "MetaData",
        {
            **ugc_video_item["metadata"],
            "title": favourite_title,
            "show_title": favourite_title,
        },
    )
    normalized_item = cast(
        "UgcVideoListItem",
        {
            **ugc_video_item,
            "name": favourite_title,
            "metadata": metadata,
        },
    )
    return normalized_item, FAVOURITE_SINGLE_PAGE_TEMPLATE, None
