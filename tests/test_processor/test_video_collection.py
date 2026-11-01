from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from urllib.parse import parse_qs, urlparse

import pytest
from returns.result import Success

from yutto.core.execution import ExecutionScope
from yutto.extractor.ugc_video import UgcVideoExtractor
from yutto.extractor.ugc_video_batch import UgcVideoBatchExtractor
from yutto.types import BvId, ExtractorOptions, MId, SeriesId
from yutto.utils.fetcher import Fetcher
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from yutto.api.collection import CollectionDetails

VIDEO = "BV1aZ421m7it"
OTHER = "BV1ct4y1o738"


@pytest.mark.processor
@pytest.mark.parametrize(
    ("has_collection", "batch", "selection", "expected"),
    [
        (True, True, "1~$", [VIDEO, OTHER]),
        (True, True, "2", [OTHER]),
        (True, False, "1~$", [VIDEO]),
        (False, True, "1~$", [VIDEO, VIDEO]),
    ],
)
@as_sync
async def test_video_entry_expands_collection_only_in_batch_mode(
    monkeypatch: pytest.MonkeyPatch,
    has_collection: bool,
    batch: bool,
    selection: str,
    expected: list[str],
):
    async def fetch_json(scope: ExecutionScope, url: str):
        if "/x/tag/" in url:
            return Success({"code": 0, "data": []})
        bvid = parse_qs(urlparse(url).query)["bvid"][0]
        data: dict[str, Any] = {
            "aid": 1 if bvid == VIDEO else 2,
            "bvid": bvid,
            "pic": "https://example.com/cover.jpg",
            "title": f"title-{bvid}",
            "pubdate": 1700000000,
            "desc": "description",
            "pages": [{"cid": 10, "part": "第一课"}],
            "owner": {"mid": 277276709, "name": "洋桃电子", "face": ""},
        }
        if has_collection:
            data["ugc_season"] = {"mid": 277276709, "id": 1852078}
        else:
            data["pages"].append({"cid": 11, "part": "第二课"})
        return Success({"code": 0, "data": data})

    collection_calls = []

    async def collection_details(scope: ExecutionScope, series_id: SeriesId, mid: MId) -> CollectionDetails:
        collection_calls.append((str(mid), str(series_id)))
        return {
            "title": "电子大百科",
            "pages": [
                {"id": 1, "title": "", "avid": BvId(VIDEO)},
                {"id": 2, "title": "", "avid": BvId(OTHER)},
            ],
        }

    async def username(scope: ExecutionScope, mid: MId):
        return "洋桃电子"

    async def touch(scope: ExecutionScope, url: str):
        return Success(None)

    monkeypatch.setattr(Fetcher, "fetch_json", fetch_json)
    monkeypatch.setattr(Fetcher, "touch_url", touch)
    monkeypatch.setattr("yutto.extractor.collection.get_collection_details", collection_details)
    monkeypatch.setattr("yutto.extractor.collection.get_user_name", username)
    options: ExtractorOptions = {
        "episodes": selection,
        "with_extra_episodes": False,
        "skip_preview": False,
        "require_video": True,
        "require_audio": True,
        "require_danmaku": False,
        "require_subtitle": False,
        "subtitle_languages": None,
        "require_metadata": False,
        "require_cover": False,
        "require_chapter_info": False,
        "danmaku_format": "ass",
        "subpath_template": "{auto}",
        "ai_translation_language": None,
        "publication_time_filter": PublicationTimeFilter.from_strings(),
    }
    extractor = UgcVideoBatchExtractor() if batch else UgcVideoExtractor()
    assert extractor.match(f"https://www.bilibili.com/video/{VIDEO}/?spm_id_from=333.1387")
    scope = ExecutionScope(cast("Any", object()))
    listed = []
    if isinstance(extractor, UgcVideoBatchExtractor):

        async def on_item(item):
            listed.append(item)

        outcome = await extractor.extract(scope, options, on_item=on_item)
    else:
        outcome = await extractor.extract(scope, options)

    assert [str(item.info["listing"].avid) for item in outcome.items] == expected
    assert outcome.failures == ()
    if has_collection and batch:
        assert collection_calls == [("277276709", "1852078")]
        assert listed == list(outcome.items)
        assert all(str(item.info["path"]).replace("\\", "/").startswith("电子大百科/") for item in outcome.items)
    else:
        assert collection_calls == []
    if not has_collection:
        assert [item.info["listing"].name for item in outcome.items] == ["第一课", "第二课"]
