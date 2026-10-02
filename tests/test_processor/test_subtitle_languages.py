from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success

import yutto.download_manager as manager_module
import yutto.extractor.bangumi as bangumi_module
import yutto.extractor.cheese as cheese_module
import yutto.extractor.ugc_video as ugc_module
from yutto.api.bangumi import get_bangumi_subtitles
from yutto.api.cheese import get_cheese_subtitles
from yutto.api.ugc_video import get_ugc_video_subtitles
from yutto.cli.cli import add_download_arguments
from yutto.cli.request_adapter import download_request_from_namespace
from yutto.cli.settings import YuttoSettings
from yutto.core.execution import ExecutionScope
from yutto.core.result import ArtifactKind, ItemState
from yutto.download_manager import DownloadManager
from yutto.types import AId, CId, EpisodeId, SeasonId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functional import as_sync
from yutto.utils.subtitle import matches_subtitle_language

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.processor

# Codes (lan) deliberately differ from labels (lan_doc), which remain the file names.
SUBTITLES = [
    ("zh-CN", "中文（中国）"),
    ("zh-Hans", "简体中文"),
    ("zh-Hant", "繁體中文"),
    ("ai-zh", "中文（自动生成）"),
    ("en", "英文"),
    ("en-US", "英语（美国）"),
    ("ai-en", "英文（自动生成）"),
    ("es", "西班牙语"),
    ("pt-BR", "葡萄牙语"),
    ("", "未知语言"),
]


@pytest.mark.parametrize(
    ("code", "languages", "matches"),
    [
        ("zh-Hans", ["zh"], True),
        ("zh-Hant", ["zh"], True),
        ("ai-zh", ["zh"], True),
        ("ai-zh-CN", ["zh-CN"], True),
        ("en-US", ["zh", "en"], True),
        ("AI-EN", [" en "], True),
        ("pt-BR", ["PT"], True),
        ("zh-Hant", ["zh-Hans"], False),
        ("zh-Hans", ["ai-zh"], False),
        ("ai-zh", ["ai-zh"], True),
        ("zho", ["zh"], False),
        ("eng", ["en"], False),
        ("", ["zh"], False),
        ("es", ["zh", "en"], False),
        ("es", [], True),
        ("", [], True),
    ],
)
def test_language_code_matching(code: str, languages: list[str], matches: bool):
    assert matches_subtitle_language(code, languages) is matches


@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/video/av1",
        "https://www.bilibili.com/bangumi/play/ep1",
        "https://www.bilibili.com/cheese/play/ep1",
    ],
    ids=["ugc", "bangumi", "cheese"],
)
@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], list(range(10))),
        (["--subtitle-languages", "all"], list(range(10))),
        (["--subtitle-languages", "zh"], [0, 1, 2, 3]),
        (["--subtitle-languages", "zh,en"], [0, 1, 2, 3, 4, 5, 6]),
        (["--subtitle-languages", "zh-CN"], [0]),
        (["--subtitle-languages", "ai-zh"], [3]),
        (["--subtitle-languages", "ja"], []),
        (["--subtitle-languages", "zh,en", "--no-subtitle"], []),
    ],
)
@as_sync
async def test_selected_subtitles_flow_from_cli_to_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, url: str, arguments: list[str], expected: list[int]
):
    async def get_list(scope: ExecutionScope, *ids: object) -> dict[str, Any]:
        return {
            "title": "series",
            "avid": AId("1"),
            "pubdate": 0,
            "pages": [
                {
                    "id": 1,
                    "name": "episode",
                    "avid": AId("1"),
                    "cid": CId("1"),
                    "episode_id": EpisodeId("1"),
                    "duration": 1000,
                    "is_section": False,
                    "is_preview": False,
                    "metadata": {
                        "actor": [],
                        "tag": [],
                        "thumb": "",
                        "dateadded": 0,
                        "premiered": 0,
                    },
                }
            ],
        }

    async def get_season_id(scope: ExecutionScope, episode_id: EpisodeId) -> SeasonId:
        return SeasonId("1")

    async def validate_user_info(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        return True

    async def redirect(scope: ExecutionScope, url: str) -> Success[str]:
        return Success(url)

    fetched_urls: list[str] = []
    subtitle_list = [
        {"lan": code, "lan_doc": label, "subtitle_url": f"//subtitles.test/{index}"}
        for index, (code, label) in enumerate(SUBTITLES)
    ]
    del subtitle_list[-1]["lan"]

    async def fetch_json(scope: ExecutionScope, url: str) -> Success[Any]:
        fetched_urls.append(url)
        if url.startswith("https://api.bilibili.com/x/player/"):
            return Success({"data": {"subtitle": {"subtitles": subtitle_list}}})
        assert url.startswith("https://subtitles.test/")
        return Success({"body": [{"from": 0, "to": 1, "content": f"line from {url}"}]})

    monkeypatch.setattr(ugc_module, "get_ugc_video_list", get_list)
    monkeypatch.setattr(bangumi_module, "get_bangumi_list", get_list)
    monkeypatch.setattr(cheese_module, "get_cheese_list", get_list)
    monkeypatch.setattr(bangumi_module, "get_season_id_by_episode_id", get_season_id)
    monkeypatch.setattr(cheese_module, "get_season_id_by_episode_id", get_season_id)
    monkeypatch.setattr(manager_module, "validate_user_info", validate_user_info)
    monkeypatch.setattr(Fetcher, "get_redirected_url", redirect)
    monkeypatch.setattr(Fetcher, "fetch_json", fetch_json)
    parser = argparse.ArgumentParser()
    add_download_arguments(parser, YuttoSettings())
    request = download_request_from_namespace(
        parser.parse_args([url, "--subtitle-only", "--dir", str(tmp_path), *arguments])
    )

    results = await DownloadManager().process_request(ExecutionScope(cast("Any", object())), request)

    assert len(results) == 1
    assert results[0].state is ItemState.DONE
    artifacts = results[0].artifacts
    assert len(artifacts) == len(expected)
    assert set(tmp_path.rglob("*.srt")) == {artifact.path for artifact in artifacts}
    for artifact, index in zip(artifacts, expected, strict=True):
        assert artifact.kind is ArtifactKind.SUBTITLE
        assert artifact.path.name.endswith(f".{SUBTITLES[index][1]}.srt")
        text = artifact.path.read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:01,000" in text
        assert f"line from https://subtitles.test/{index}" in text
    assert [url for url in fetched_urls if url.startswith("https://subtitles.test/")] == [
        f"https://subtitles.test/{index}" for index in expected
    ]
    assert sum(url.startswith("https://api.bilibili.com/x/player/") for url in fetched_urls) == int(
        request.resources.subtitle
    )


@pytest.mark.parametrize("get_subtitles", [get_ugc_video_subtitles, get_bangumi_subtitles, get_cheese_subtitles])
@as_sync
async def test_subtitle_filter_preserves_invalid_url_and_missing_body_handling(
    monkeypatch: pytest.MonkeyPatch, get_subtitles
):
    fetched_urls: list[str] = []

    async def fetch_json(scope: ExecutionScope, url: str) -> Success[Any]:
        fetched_urls.append(url)
        if url.startswith("https://api.bilibili.com/"):
            return Success(
                {
                    "data": {
                        "subtitle": {
                            "subtitles": [
                                {"lan": "zh", "lan_doc": "中文", "subtitle_url": None},
                                {"lan": "zh", "lan_doc": "中文", "subtitle_url": " "},
                                {"lan": "zh", "lan_doc": "中文", "subtitle_url": "//subtitles.test/missing"},
                                {"lan": "en", "lan_doc": "英文", "subtitle_url": "//subtitles.test/excluded"},
                            ]
                        }
                    }
                }
            )
        assert url == "https://subtitles.test/missing"
        return Success(None)

    monkeypatch.setattr(Fetcher, "fetch_json", fetch_json)
    subtitles = await get_subtitles(ExecutionScope(cast("Any", object())), AId("1"), CId("1"), ["zh"])

    assert subtitles == []
    assert len(fetched_urls) == 2
