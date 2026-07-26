from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from yutto.core.result import (
    Artifact,
    ArtifactKind,
    DownloadResult,
    ItemResult,
    ItemSkipReason,
    ItemState,
    ResolvedItem,
)
from yutto.types import AId, CId

pytestmark = pytest.mark.processor


def test_result_models_are_frozen_and_reject_extra_fields():
    result = DownloadResult()

    with pytest.raises(ValidationError, match="frozen"):
        result.items = ()  # ty: ignore[invalid-assignment]
    with pytest.raises(ValidationError, match="Extra inputs"):
        Artifact(kind=ArtifactKind.MEDIA, path=Path("video.mp4"), size=1)  # ty: ignore[unknown-argument]


def test_resolved_item_is_a_typed_immutable_listing_snapshot():
    payload: dict[str, object] = {
        "avid": AId("1"),
        "cid": CId("10"),
        "url": "https://www.bilibili.com/video/av1?p=1",
        "name": "P1",
        "title": "标题",
        "cover_url": "https://example.com/cover.jpg",
        "planned_path": Path("标题/P1"),
        "display_group": "标题",
        "uploader": "某UP主",
        "description": "视频简介",
        "tags": ("标签A", "标签B"),
    }
    item = ResolvedItem.model_validate(payload)

    assert isinstance(item.avid, AId)
    assert isinstance(item.cid, CId)
    assert item.tags == ("标签A", "标签B")
    assert set(type(item).model_fields) == set(payload)
    serialized = item.model_dump(mode="json")
    assert serialized["avid"] == "1"
    assert serialized["cid"] == "10"
    assert serialized["planned_path"] == "标题/P1"
    assert serialized["tags"] == ["标签A", "标签B"]
    schema = ResolvedItem.model_json_schema(mode="serialization")
    assert schema["properties"]["avid"]["type"] == "string"
    assert schema["properties"]["cid"]["type"] == "string"

    with pytest.raises(ValidationError, match="frozen"):
        item.name = "changed"  # ty: ignore[invalid-assignment]
    with pytest.raises(ValidationError, match="Extra inputs"):
        ResolvedItem.model_validate({**payload, "play_url": "https://example.com/expiring"})


def test_item_result_validates_skip_reason_without_requiring_artifacts():
    resource_only = ItemResult(state=ItemState.DONE, output_path=Path("video.mp4"))
    media_download = ItemResult(
        state=ItemState.DONE,
        output_path=Path("video.mp4"),
        artifacts=(Artifact(kind=ArtifactKind.MEDIA, path=Path("video.mp4")),),
    )
    existing_media = ItemResult(
        state=ItemState.SKIPPED,
        output_path=Path("video.mp4"),
        skip_reason=ItemSkipReason.ALREADY_EXISTS,
        artifacts=(Artifact(kind=ArtifactKind.MEDIA, path=Path("video.mp4")),),
    )

    assert resource_only.artifacts == ()
    assert resource_only.has_downloaded_media is False
    assert media_download.has_downloaded_media is True
    assert existing_media.has_downloaded_media is False
    assert (
        ItemResult(
            state=ItemState.SKIPPED,
            output_path=Path("video.mp4"),
            skip_reason=ItemSkipReason.NO_MEDIA_STREAM,
        ).skip_reason
        is ItemSkipReason.NO_MEDIA_STREAM
    )

    with pytest.raises(ValidationError, match="done item must not have"):
        ItemResult(
            state=ItemState.DONE,
            output_path=Path("video.mp4"),
            skip_reason=ItemSkipReason.ALREADY_EXISTS,
        )
    with pytest.raises(ValidationError, match="skipped item must have"):
        ItemResult(state=ItemState.SKIPPED, output_path=Path("video.mp4"))
