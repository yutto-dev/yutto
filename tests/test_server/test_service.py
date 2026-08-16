from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

import yutto.core.execution as execution_module
from yutto.auth import load_auth
from yutto.core.events import DownloadItemListed
from yutto.core.execution import RequestExecutionScopeFactory
from yutto.core.request import DownloadRequest
from yutto.core.result import (
    Artifact,
    ArtifactKind,
    DownloadResult,
    ItemResult,
    ItemState,
    ResolvedItem,
    ResolveResult,
)
from yutto.core.task_service import _encode_runtime_event
from yutto.runtime import EventReplay, TaskError, TaskEvent, TaskSnapshot, TaskState
from yutto.server.service import (
    ServerPolicy,
    ServerPolicyError,
    ServerPolicyOptions,
    event_to_json,
    replay_to_json,
    snapshot_summary_to_json,
    snapshot_to_json,
)
from yutto.types import AId, CId
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


def make_policy(
    tmp_path: Path,
    *,
    max_fetch_workers: int = 8,
    max_download_workers: int = 8,
) -> ServerPolicy:
    return ServerPolicy(
        ServerPolicyOptions(
            download_root=tmp_path / "downloads",
            tmp_root=tmp_path / "temporary",
            auth_file=tmp_path / "auth.toml",
            max_fetch_workers=max_fetch_workers,
            max_download_workers=max_download_workers,
        )
    )


def make_request(**overrides: object) -> DownloadRequest:
    payload: dict[str, object] = {"source": {"url": "BV1server"}}
    payload.update(overrides)
    return DownloadRequest.model_validate(payload)


def test_prepare_request_resolves_output_paths_under_server_roots(tmp_path: Path):
    policy = make_policy(tmp_path)
    request = make_request(
        output={
            "directory": "shows/season-1",
            "temporary_directory": "segments/task-1",
        }
    )

    prepared = policy.prepare_request(request)

    assert prepared.output.directory == (tmp_path / "downloads/shows/season-1").resolve()
    assert prepared.output.temporary_directory == (tmp_path / "temporary/segments/task-1").resolve()
    assert request.output.directory == Path("shows/season-1")
    assert request.output.temporary_directory == Path("segments/task-1")


def test_prepare_request_uses_configured_roots_for_default_paths(tmp_path: Path):
    policy = make_policy(tmp_path)

    prepared = policy.prepare_request(make_request())

    assert prepared.output.directory == (tmp_path / "downloads").resolve()
    assert prepared.output.temporary_directory == (tmp_path / "temporary").resolve()


@pytest.mark.parametrize(
    ("output", "message"),
    [
        ({"directory": "/outside"}, "output.directory must be relative"),
        ({"directory": "safe/../outside"}, "output.directory must not contain"),
        ({"temporary_directory": "/outside"}, "output.temporary_directory must be relative"),
        ({"temporary_directory": "safe/../../outside"}, "output.temporary_directory must not contain"),
    ],
)
def test_prepare_request_rejects_absolute_and_parent_paths(tmp_path: Path, output: object, message: str):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match=message):
        policy.prepare_request(make_request(output=output))


def test_prepare_request_rejects_existing_symlink_escape(tmp_path: Path):
    policy = make_policy(tmp_path)
    policy.options.download_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (policy.options.download_root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ServerPolicyError, match="escapes its configured root"):
        policy.prepare_request(make_request(output={"directory": "linked/result"}))


@pytest.mark.parametrize("template", ["../outside/{title}", "safe/../../outside", "/outside/{title}"])
def test_prepare_request_rejects_subpath_template_escape(tmp_path: Path, template: str):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match="subpath_template"):
        policy.prepare_request(make_request(output={"subpath_template": template}))


@pytest.mark.parametrize("template", ["{id:/>10}", "{title:.^2.0}/outside", "{title!x}", "{id:0>1000}"])
def test_prepare_request_rejects_advanced_format_template_escape(tmp_path: Path, template: str):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match="subpath_template"):
        policy.prepare_request(make_request(output={"subpath_template": template}))


def test_prepare_request_marks_final_output_path_for_boundary_enforcement(tmp_path: Path):
    policy = make_policy(tmp_path)

    prepared = policy.prepare_request(
        make_request(output={"subpath_template": "series/{pubdate@%Y-%m-%d %H:%M:%S}/{id:0>3}{title}"})
    )

    assert prepared.output.enforce_directory_boundary is True
    assert "enforce_directory_boundary" not in prepared.model_dump(mode="json")["output"]


@pytest.mark.parametrize(
    "network",
    [
        {"fetch_workers": 0},
        {"fetch_workers": 5},
        {"download_workers": 0},
        {"download_workers": 7},
    ],
)
def test_policy_rejects_worker_counts_outside_configured_limits(tmp_path: Path, network: object):
    policy = make_policy(tmp_path, max_fetch_workers=4, max_download_workers=6)

    with pytest.raises(ServerPolicyError, match="must be between 1 and"):
        policy.prepare_request(make_request(network=network))


def test_prepare_request_rejects_invalid_auth_profile(tmp_path: Path):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match="auth profile 名称不合法"):
        policy.prepare_request(make_request(access={"auth_profile": "bad profile"}))


@pytest.mark.parametrize("block_size", [0, -1, 64 * 1024 - 1, 64 * 1024 * 1024 + 1])
def test_policy_rejects_unsafe_block_sizes(tmp_path: Path, block_size: int):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match="block_size_bytes"):
        policy.prepare_request(make_request(network={"block_size_bytes": block_size}))


def test_policy_rejects_ffmpeg_save_codecs_outside_server_capabilities(tmp_path: Path):
    policy = ServerPolicy(
        ServerPolicyOptions(
            download_root=tmp_path / "downloads",
            tmp_root=tmp_path / "temporary",
            auth_file=tmp_path / "auth.toml",
            allowed_video_save_codecs=frozenset({"copy", "h264"}),
            allowed_audio_save_codecs=frozenset({"copy", "aac"}),
        )
    )

    with pytest.raises(ServerPolicyError, match="video save codec"):
        policy.prepare_request(make_request(stream={"video_save_codec": "av1"}))
    with pytest.raises(ServerPolicyError, match="audio save codec"):
        policy.prepare_request(make_request(stream={"audio_save_codec": "flac"}))


@pytest.mark.parametrize("field", ["max_fetch_workers", "max_download_workers"])
def test_options_reject_non_positive_worker_limits(tmp_path: Path, field: str):
    options = {
        "download_root": tmp_path / "downloads",
        "tmp_root": tmp_path / "temporary",
        "auth_file": tmp_path / "auth.toml",
        field: 0,
    }

    with pytest.raises(ValueError, match=f"{field} must be at least 1"):
        ServerPolicyOptions(**options)  # ty: ignore[invalid-argument-type]


@as_sync
async def test_scope_factory_applies_request_network_and_selected_auth_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    policy = make_policy(tmp_path, max_fetch_workers=4)
    policy.options.auth_file.write_text(
        """
[profiles.default]
sessdata = "not-selected"

[profiles.work]
sessdata = "session,value"
bili_jct = "csrf-value"
""".strip(),
        encoding="utf-8",
    )
    request = make_request(
        access={"auth_profile": "work"},
        network={"proxy": "no", "fetch_workers": 3},
    )
    captured: dict[str, object] = {}
    create_client = execution_module.create_client

    @asynccontextmanager
    async def capture_client(**kwargs):
        captured.update(kwargs)
        async with create_client(**kwargs) as session:
            yield session

    monkeypatch.setattr(execution_module, "create_client", capture_client)

    async with policy.build_scope_factory().open(request) as scope:
        assert captured["trust_env"] is False
        assert scope.fetch_limiter._value == 3
        assert scope.session.cookie("SESSDATA") == "session%2Cvalue"
        assert scope.session.cookie("bili_jct") == "csrf-value"


@as_sync
async def test_cli_and_server_scope_factories_interpret_same_request_equivalently(tmp_path: Path):
    policy = make_policy(tmp_path)
    policy.options.auth_file.write_text(
        """
[profiles.work]
sessdata = "session,value"
bili_jct = "csrf-value"
""".strip(),
        encoding="utf-8",
    )
    request = make_request(
        access={"auth_profile": "work"},
        network={
            "proxy": "no",
            "fetch_workers": 3,
            "download_workers": 4,
        },
    )
    cli_factory = RequestExecutionScopeFactory(
        lambda active_request: load_auth(
            policy.options.auth_file,
            active_request.access.auth_profile,
        )
    )

    async with (
        cli_factory.open(request) as cli_scope,
        policy.build_scope_factory().open(request) as server_scope,
    ):
        assert (
            cli_scope.fetch_limiter._value,
            cli_scope.download_workers,
            cli_scope.session.cookie("SESSDATA"),
            cli_scope.session.cookie("bili_jct"),
        ) == (
            server_scope.fetch_limiter._value,
            server_scope.download_workers,
            server_scope.session.cookie("SESSDATA"),
            server_scope.session.cookie("bili_jct"),
        )


def test_scope_factory_rejects_invalid_auth_profile_without_exposing_auth_file(tmp_path: Path):
    policy = make_policy(tmp_path)

    with pytest.raises(ServerPolicyError, match="auth profile"):
        policy.resolve_credentials(make_request(access={"auth_profile": "bad profile"}))


class CredentialPayload(BaseModel):
    url: str
    auth_profile: str
    SESSDATA: str
    nested: dict[str, str]


def test_snapshot_serialization_is_json_compatible_and_removes_credentials():
    created_at = datetime(2026, 7, 12, 10, 11, 12, tzinfo=UTC)
    payload = CredentialPayload(
        url="BV1safe",
        auth_profile="work",
        SESSDATA="session-secret",
        nested={"token": "token-secret", "visible": "kept"},
    )
    snapshot = TaskSnapshot[object, object](
        task_id="task-1",
        state=TaskState.FAILED,
        payload=payload,
        result=None,
        error=TaskError(type="ExampleError", message="failed"),
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at,
        last_event_seq=4,
    )

    serialized = snapshot_to_json(snapshot)

    assert serialized == {
        "task_id": "task-1",
        "state": "failed",
        "payload": {
            "url": "BV1safe",
            "auth_profile": "work",
            "nested": {"visible": "kept"},
        },
        "result": None,
        "error": {"code": "internal_error", "type": "ExampleError", "message": "failed"},
        "created_at": "2026-07-12T10:11:12+00:00",
        "started_at": "2026-07-12T10:11:12+00:00",
        "finished_at": "2026-07-12T10:11:12+00:00",
        "last_event_seq": 4,
    }
    assert "secret" not in json.dumps(serialized)
    assert snapshot_summary_to_json(snapshot)["error"] == {
        "code": "internal_error",
        "type": "ExampleError",
    }


def test_request_snapshot_removes_proxy_userinfo():
    created_at = datetime(2026, 7, 12, 10, 11, 12, tzinfo=UTC)
    snapshot = TaskSnapshot[DownloadRequest, None](
        task_id="task-proxy",
        state=TaskState.QUEUED,
        payload=make_request(network={"proxy": "http://proxy-user:proxy-password@example.test:8080"}),
        result=None,
        error=None,
        created_at=created_at,
        started_at=None,
        finished_at=None,
        last_event_seq=1,
    )

    serialized = snapshot_to_json(snapshot)
    network = cast("dict[str, object]", cast("dict[str, object]", serialized["payload"])["network"])

    assert network["proxy"] == "http://example.test:8080"
    assert "proxy-password" not in json.dumps(serialized)


def test_download_result_serializes_paths_enums_and_tuples():
    created_at = datetime(2026, 7, 12, 10, 11, 12, tzinfo=UTC)
    result = DownloadResult(
        items=(
            ItemResult(
                state=ItemState.DONE,
                output_path=Path("series/video.mp4"),
                artifacts=(Artifact(kind=ArtifactKind.MEDIA, path=Path("series/video.mp4")),),
            ),
        )
    )
    snapshot = TaskSnapshot[DownloadRequest, DownloadResult](
        task_id="task-result",
        state=TaskState.COMPLETED,
        payload=make_request(),
        result=result,
        error=None,
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at,
        last_event_seq=3,
    )

    serialized = snapshot_to_json(snapshot)

    assert serialized["result"] == {
        "items": [
            {
                "state": "done",
                "output_path": "series/video.mp4",
                "skip_reason": None,
                "artifacts": [{"kind": "media", "path": "series/video.mp4"}],
            }
        ]
    }


def test_listing_event_and_result_share_jsonrpc_wire_shape():
    created_at = datetime(2026, 7, 12, 11, 12, 13, tzinfo=UTC)

    def serialize_both(item: ResolvedItem) -> tuple[dict[str, object], dict[str, object]]:
        kind, data = _encode_runtime_event(DownloadItemListed(item=item))
        event = TaskEvent(
            task_id="task-listing",
            seq=1,
            kind=kind,
            state=TaskState.RUNNING,
            created_at=created_at,
            data=data,
        )
        snapshot = TaskSnapshot[DownloadRequest, ResolveResult](
            task_id="task-listing",
            state=TaskState.COMPLETED,
            payload=make_request(),
            result=ResolveResult(items=(item,)),
            error=None,
            created_at=created_at,
            started_at=created_at,
            finished_at=created_at,
            last_event_seq=1,
        )
        event_wire = cast("dict[str, object]", event_to_json(event)["data"])
        result = cast("dict[str, object]", snapshot_to_json(snapshot)["result"])
        result_wire = cast("list[dict[str, object]]", result["items"])[0]
        return event_wire, result_wire

    item = ResolvedItem(
        avid=AId("1"),
        cid=CId("10"),
        url="https://www.bilibili.com/video/av1?p=1",
        name="P1",
        title="标题",
        cover_url="https://example.com/cover.jpg",
        planned_path=Path("标题/P1"),
        display_group="标题",
        uploader="某UP主",
        description="视频简介",
        tags=("标签A", "标签B"),
        pubdate=1698148800,
        duration=1559,
    )
    expected = {
        "avid": "1",
        "cid": "10",
        "url": "https://www.bilibili.com/video/av1?p=1",
        "name": "P1",
        "title": "标题",
        "cover_url": "https://example.com/cover.jpg",
        "planned_path": "标题/P1",
        "display_group": "标题",
        "uploader": "某UP主",
        "description": "视频简介",
        "tags": ["标签A", "标签B"],
        "pubdate": 1698148800,
        "duration": 1559,
    }
    event_wire, result_wire = serialize_both(item)

    assert event_wire == result_wire == expected
    assert type(event_wire["avid"]) is str
    assert type(event_wire["planned_path"]) is str
    assert type(event_wire["tags"]) is list
    assert type(event_wire["pubdate"]) is int
    assert type(event_wire["duration"]) is int

    default_item = ResolvedItem(
        avid=AId("2"),
        cid=CId("20"),
        url="https://www.bilibili.com/video/av2?p=1",
        name="单集",
        title="单集",
        cover_url="",
        planned_path=Path("单集"),
    )
    default_expected = {
        "avid": "2",
        "cid": "20",
        "url": "https://www.bilibili.com/video/av2?p=1",
        "name": "单集",
        "title": "单集",
        "cover_url": "",
        "planned_path": "单集",
        "display_group": None,
        "uploader": "",
        "description": "",
        "tags": [],
        "pubdate": 0,
        "duration": 0,
    }

    assert serialize_both(default_item) == (default_expected, default_expected)


def test_event_and_replay_serialization_use_enum_values_iso_dates_and_redaction():
    created_at = datetime(2026, 7, 12, 11, 12, 13, tzinfo=UTC)
    event = TaskEvent(
        task_id="task-2",
        seq=8,
        kind="progress",
        state=TaskState.RUNNING,
        created_at=created_at,
        data={
            "phase": TaskState.RUNNING,
            "observed_at": created_at,
            "cookies": {"SESSDATA": "session-secret"},
            "steps": (1, 2),
        },
    )
    replay = EventReplay(task_id="task-2", after_seq=3, events=(event,), truncated=True)

    serialized_event = event_to_json(event)
    serialized_replay = replay_to_json(replay)

    assert serialized_event == {
        "task_id": "task-2",
        "seq": 8,
        "kind": "progress",
        "state": "running",
        "created_at": "2026-07-12T11:12:13+00:00",
        "data": {
            "phase": "running",
            "observed_at": "2026-07-12T11:12:13+00:00",
            "steps": [1, 2],
        },
    }
    assert type(cast("dict[str, object]", serialized_event["data"])["phase"]) is str
    assert serialized_replay == {
        "task_id": "task-2",
        "after_seq": 3,
        "events": [serialized_event],
        "truncated": True,
    }
    json.dumps(serialized_replay)
