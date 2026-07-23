from __future__ import annotations

import pytest

from yutto.path_templates import (
    MpTitlePreset,
    build_mp_title,
    sanitize_multi_version_name,
    strip_contained_title,
)

pytestmark = pytest.mark.processor


def test_strip_contained_title_removes_full_title_once():
    title = "【SING女团】炙热的我们首秀舞台：女侠风《大碗宽面》飒爽上线"
    name = f"{title}完整舞蹈版"
    assert strip_contained_title(name, title) == "完整舞蹈版"


def test_build_mp_title_single_p_always_uses_title():
    assert (
        build_mp_title(
            title="总标题",
            name="分P标题",
            part_id=2,
            preset="title-dot-name",
            is_multi_p=False,
        )
        == "总标题"
    )


def test_build_mp_title_presets_for_multi_p():
    title = "【SING女团】炙热的我们首秀舞台：女侠风《大碗宽面》飒爽上线"
    name = "完整舞蹈版"
    cases: list[tuple[MpTitlePreset, str]] = [
        ("title", title),
        ("name", name),
        ("title-dot-name", f"{title}.{name}"),
        ("title-dot-name-with-id", f"{title}.p2.{name}"),
        ("title-hyphen-name", f"{title}-{name}"),
        ("title-hyphen-name-with-id", f"{title}-p2-{name}"),
        ("title-hyphen-space-name", f"{title} - {name}"),
        ("title-hyphen-space-name-with-id", f"{title} - p2 - {name}"),
    ]
    for preset, expected in cases:
        assert (
            build_mp_title(
                title=title,
                name=name,
                part_id=2,
                preset=preset,
                is_multi_p=True,
            )
            == expected
        )


def test_build_mp_title_strips_title_overlap_for_combined_presets():
    title = "总标题"
    name = "总标题 - 分P"
    assert (
        build_mp_title(
            title=title,
            name=name,
            part_id=1,
            preset="title-hyphen-space-name",
            is_multi_p=True,
        )
        == "总标题 - 分P"
    )


def test_sanitize_multi_version_name_replaces_symbols():
    assert sanitize_multi_version_name("A:B/C 测试!") == "A_B_C_测试"
