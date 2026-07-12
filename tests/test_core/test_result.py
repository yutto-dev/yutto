from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from yutto.core.result import Artifact, ArtifactKind, DownloadResult, ItemResult, ItemSkipReason, ItemState

pytestmark = pytest.mark.processor


def test_result_models_are_frozen_and_reject_extra_fields():
    result = DownloadResult()

    with pytest.raises(ValidationError, match="frozen"):
        result.items = ()  # ty: ignore[invalid-assignment]
    with pytest.raises(ValidationError, match="Extra inputs"):
        Artifact(kind=ArtifactKind.MEDIA, path=Path("video.mp4"), size=1)  # ty: ignore[unknown-argument]


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
