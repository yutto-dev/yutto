from __future__ import annotations

from pathlib import Path

from yutto.input_parser import alias_parser


def test_alias_separator_keeps_the_real_url(tmp_path: Path):
    alias_file = tmp_path / "aliases"
    alias_file.write_text(
        "\n".join(
            [
                "tight=https://www.bilibili.com/bangumi/play/ss25739/",
                "spaced = https://www.bilibili.com/bangumi/play/ss36170/",
                "after= https://www.bilibili.com/bangumi/play/ss38221/?q=1",
                "double  https://www.bilibili.com/video/BV1double",
                "single https://www.bilibili.com/video/BV1single",
                "# comment",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert alias_parser(str(alias_file)) == {
        "tight": "https://www.bilibili.com/bangumi/play/ss25739/",
        "spaced": "https://www.bilibili.com/bangumi/play/ss36170/",
        "after": "https://www.bilibili.com/bangumi/play/ss38221/?q=1",
        "double": "https://www.bilibili.com/video/BV1double",
        "single": "https://www.bilibili.com/video/BV1single",
    }
