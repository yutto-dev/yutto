from __future__ import annotations

from pathlib import Path

from yutto.input_parser import file_scheme_parser


def test_utf8_bom_keeps_the_first_task_list_entry(tmp_path: Path):
    plain = tmp_path / "plain.txt"
    plain.write_text("https://www.bilibili.com/video/BV1plain\n# comment\n\n", encoding="utf-8")
    bom = tmp_path / "bom.txt"
    bom.write_bytes(
        b"\xef\xbb\xbfhttps://www.bilibili.com/video/BV1first\n# comment\nhttps://www.bilibili.com/video/BV1second\n"
    )

    assert file_scheme_parser(str(plain)) == ["https://www.bilibili.com/video/BV1plain"]
    assert file_scheme_parser(str(bom)) == [
        "https://www.bilibili.com/video/BV1first",
        "https://www.bilibili.com/video/BV1second",
    ]
