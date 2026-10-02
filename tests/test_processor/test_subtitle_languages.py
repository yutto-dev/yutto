from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success

from yutto.api.bangumi import get_bangumi_subtitles
from yutto.api.cheese import get_cheese_subtitles
from yutto.api.ugc_video import get_ugc_video_subtitles
from yutto.core.execution import ExecutionScope
from yutto.types import AId, CId
from yutto.utils.fetcher import Fetcher
from yutto.utils.functional import as_sync
from yutto.utils.subtitle import matches_subtitle_language

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from yutto.types import MultiLangSubtitle

pytestmark = pytest.mark.processor


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
        ("es", ["zh", "en"], False),
        ("es", [], False),
        ("es", None, True),
    ],
)
def test_language_code_matching(code: str, languages: list[str] | None, matches: bool):
    assert matches_subtitle_language(code, languages) is matches


@pytest.mark.parametrize("get_subtitles", [get_ugc_video_subtitles, get_bangumi_subtitles, get_cheese_subtitles])
@pytest.mark.parametrize(
    ("languages", "expected"),
    [
        (None, ["zh-CN", "zh-Hans", "zh-Hant", "ai-zh", "en", "es", "pt-BR"]),
        ([], []),
        (["zh"], ["zh-CN", "zh-Hans", "zh-Hant", "ai-zh"]),
        (["zh", "en"], ["zh-CN", "zh-Hans", "zh-Hant", "ai-zh", "en"]),
        (["ja"], []),
    ],
)
@as_sync
async def test_subtitle_api_filters_before_fetching_content(
    monkeypatch: pytest.MonkeyPatch,
    get_subtitles: Callable[..., Awaitable[list[MultiLangSubtitle]]],
    languages: list[str] | None,
    expected: list[str],
):
    fetched_codes: list[str] = []

    async def fetch_json(scope: ExecutionScope, url: str) -> Success[Any]:
        if url.startswith("https://api.bilibili.com/"):
            return Success(
                {
                    "data": {
                        "subtitle": {
                            "subtitles": [
                                {"lan": code, "lan_doc": f"label-{code}", "subtitle_url": f"//subtitles.test/{code}"}
                                for code in ["zh-CN", "zh-Hans", "zh-Hant", "ai-zh", "en", "es", "pt-BR"]
                            ]
                        }
                    }
                }
            )
        code = url.removeprefix("https://subtitles.test/")
        fetched_codes.append(code)
        return Success({"body": [{"from": 0, "to": 1, "content": code}]})

    monkeypatch.setattr(Fetcher, "fetch_json", fetch_json)
    scope = ExecutionScope(cast("Any", object()))
    subtitles = await get_subtitles(scope, AId("1"), CId("1"), languages)

    assert fetched_codes == expected
    assert subtitles == [
        {"lang": f"label-{code}", "lines": [{"from": 0, "to": 1, "content": code}]} for code in expected
    ]
