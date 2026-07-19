from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from itertools import count
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.typing import Origin

from yutto.core.request import DownloadRequest
from yutto.core.result import DownloadResult, ResolveResult
from yutto.extractor.utils.batch import resolve_ugc_video_lists
from yutto.runtime import TaskContext, TaskRuntime, TaskSnapshot, TaskState, monotonic_seq_allocator
from yutto.server.websocket import (
    WebSocketServerOptions,
    YuttoWebSocketServer,
    _SlowConsumerCloser,
    _task_snapshot_order,
)
from yutto.types import AId
from yutto.utils.fetcher import Fetcher, FetcherContext
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor

if TYPE_CHECKING:
    from collections.abc import Callable

    from yutto.api.ugc_video import UgcVideoList
    from yutto.extractor.utils.batch import IndexedResolveItem
    from yutto.runtime import EventReplay, TaskEvent


class FakeDownloadTaskApi:
    def __init__(self, *, seq_allocator: Callable[[], int] | None = None) -> None:
        self.release = asyncio.Event()
        self.runtime = TaskRuntime[DownloadRequest, DownloadResult](
            self._run,
            task_id_factory=lambda: "task-1",
            seq_allocator=seq_allocator,
        )

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self, *, cancel_pending: bool = False) -> None:
        await self.runtime.close(cancel_pending=cancel_pending)

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, DownloadResult]:
        return await self.runtime.submit(request)

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, DownloadResult] | None:
        return self.runtime.get(task_id)

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, DownloadResult], ...]:
        return self.runtime.list()

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, DownloadResult] | None:
        return await self.runtime.cancel(task_id)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        return self.runtime.replay(task_id, after_seq=after_seq)

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        return self.runtime.add_event_listener(listener)

    async def _run(self, request: DownloadRequest, context: TaskContext) -> DownloadResult:
        await self.release.wait()
        context.emit("progress", {"current": 1, "total": 1})
        return DownloadResult()


class FakeResolveTaskApi:
    def __init__(self, *, item_count: int = 0, seq_allocator: Callable[[], int] | None = None) -> None:
        self.release = asyncio.Event()
        self.item_count = item_count
        ids = count(1)
        self.runtime = TaskRuntime[DownloadRequest, ResolveResult](
            self._run,
            task_id_factory=lambda: f"resolve-{next(ids)}",
            seq_allocator=seq_allocator,
        )

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self, *, cancel_pending: bool = False) -> None:
        await self.runtime.close(cancel_pending=cancel_pending)

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, ResolveResult]:
        return await self.runtime.submit(request)

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, ResolveResult] | None:
        return self.runtime.get(task_id)

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, ResolveResult], ...]:
        return self.runtime.list()

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, ResolveResult] | None:
        return await self.runtime.cancel(task_id)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        return self.runtime.replay(task_id, after_seq=after_seq)

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        return self.runtime.add_event_listener(listener)

    async def _run(self, request: DownloadRequest, context: TaskContext) -> ResolveResult:
        await self.release.wait()
        for index in range(self.item_count):
            context.emit("item_listed", {"avid": str(index), "url": f"https://example.com/{index}"})
            # 与修复后的 DownloadManager.resolve_items 一致：事件生产逐条让出控制权
            await asyncio.sleep(0)
        return ResolveResult(items=())


class BatchStreamingResolveApi(FakeResolveTaskApi):
    """经真实 resolve_ugc_video_lists 推流的 resolve 服务，复现生产端的完整事件路径"""

    def __init__(self, *, video_count: int, pages_per_video: int) -> None:
        super().__init__()
        self.video_count = video_count
        self.pages_per_video = pages_per_video

    async def _run(self, request: DownloadRequest, context: TaskContext) -> ResolveResult:
        await self.release.wait()

        async def on_resolved(resolved: IndexedResolveItem[UgcVideoList]) -> None:
            # 模拟内置提取器的回调：逐分集 emit 并让出控制权
            for page in range(self.pages_per_video):
                context.emit("item_listed", {"avid": str(resolved.source), "page": page})
                await asyncio.sleep(0)

        await resolve_ugc_video_lists(
            FetcherContext(),
            cast("Any", object()),
            [AId(str(index + 1)) for index in range(self.video_count)],
            publication_time_filter=PublicationTimeFilter.from_strings(None, None),
            on_resolved=on_resolved,
        )
        return ResolveResult(items=())


def _patch_batch_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_ugc_video_list(ctx: FetcherContext, client: Any, avid: Any):
        # 立即返回：所有视频几乎同时就绪，复现并发完成的最坏情况
        return {"title": str(avid), "pubdate": 1700000000, "avid": avid, "pages": []}

    async def fake_touch_url(ctx: FetcherContext, client: Any, url: str):
        return Success(None)

    monkeypatch.setattr("yutto.extractor.utils.batch.get_ugc_video_list", fake_get_ugc_video_list)
    monkeypatch.setattr(Fetcher, "touch_url", fake_touch_url)


def rpc_request(request_id: int, method: str, params: object | None = None) -> str:
    payload: dict[str, object] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return json.dumps(payload)


async def receive_json(connection) -> dict[str, Any]:
    message = await connection.recv()
    assert isinstance(message, str)
    payload = json.loads(message)
    assert isinstance(payload, dict)
    return payload


async def start_server(
    *,
    allowed_origins: tuple[str, ...] = (),
    token: str = "test-token",
    service: FakeDownloadTaskApi | None = None,
    resolve_service: FakeResolveTaskApi | None = None,
) -> tuple[YuttoWebSocketServer, FakeDownloadTaskApi, str]:
    service = service or FakeDownloadTaskApi()
    server = YuttoWebSocketServer(
        service,
        WebSocketServerOptions(
            token=token,
            host="127.0.0.1",
            port=0,
            allowed_origins=allowed_origins,
        ),
        resolve_service=resolve_service,
    )
    await server.start()
    port = server.sockets[0].getsockname()[1]
    return server, service, f"ws://127.0.0.1:{port}"


@pytest.mark.processor
@as_sync
async def test_slow_consumer_close_is_scheduled_only_once():
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    class SlowConnection:
        close_calls = 0

        async def close(self, *, code: int, reason: str) -> None:
            self.close_calls += 1
            assert code == 1013
            assert reason == "event consumer is too slow"
            close_started.set()
            await release_close.wait()

    connection = SlowConnection()
    closer = _SlowConsumerCloser()
    closer.schedule(cast("Any", connection))
    closer.schedule(cast("Any", connection))
    await close_started.wait()

    assert closer.scheduled is True
    assert connection.close_calls == 1

    release_close.set()
    await closer.wait()


@pytest.mark.processor
@as_sync
async def test_requires_first_message_authentication():
    server, _, uri = await start_server()
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.info"))
            response = await receive_json(connection)
            assert response == {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32601, "message": "Method not found"},
            }
            with pytest.raises(ConnectionClosedError):
                await connection.recv()
            assert connection.close_code == 1008

        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "wrong-token"}))
            response = await receive_json(connection)
            assert response["error"] == {"code": -32001, "message": "Authentication failed"}
            with pytest.raises(ConnectionClosedError):
                await connection.recv()
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_server_info_and_exact_origin_allowlist():
    server, _, uri = await start_server(allowed_origins=("https://ui.example",))
    try:
        with pytest.raises(InvalidStatus):
            async with connect(uri, origin=Origin("https://evil.example"), proxy=None):
                pass

        async with connect(uri, origin=Origin("https://ui.example"), proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            assert (await receive_json(connection))["result"] == {"authenticated": True}

            await connection.send(rpc_request(2, "server.info"))
            result = (await receive_json(connection))["result"]
            assert result["name"] == "yutto"
            assert result["protocol_version"] == 1
            assert "download.start" in result["capabilities"]

            await connection.send(rpc_request(3, "task.get", {"task_id": 123}))
            assert (await receive_json(connection))["error"] == {
                "code": -32602,
                "message": "Invalid params",
            }

            await connection.send(
                rpc_request(
                    4,
                    "download.start",
                    {
                        "request": {
                            "source": {"url": "BV1xx"},
                            "resources": {"cover": False, "save_cover": True},
                        }
                    },
                )
            )
            assert (await receive_json(connection))["error"] == {
                "code": -32602,
                "message": "Invalid params",
            }
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_download_task_lifecycle_replay_and_live_notifications():
    server, service, uri = await start_server()
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)

            await connection.send(
                rpc_request(
                    2,
                    "download.start",
                    {"request": {"source": {"url": "https://www.bilibili.com/video/BV1xx"}}},
                )
            )
            started = (await receive_json(connection))["result"]
            assert started["task_id"] == "task-1"
            assert started["state"] == "queued"

            await connection.send(rpc_request(3, "task.subscribe", {"task_id": "task-1", "after_seq": 0}))
            replay = (await receive_json(connection))["result"]
            assert replay["task_id"] == "task-1"
            assert replay["truncated"] is False
            assert replay["events"]

            service.release.set()
            terminal_notification: dict[str, Any] | None = None
            while terminal_notification is None:
                notification = await receive_json(connection)
                if notification.get("method") == "task.event" and notification["params"]["state"] == "completed":
                    terminal_notification = notification
            assert terminal_notification["params"]["kind"] == "state"

            await connection.send(rpc_request(4, "task.get", {"task_id": "task-1"}))
            completed = (await receive_json(connection))["result"]
            assert completed["state"] == "completed"
            assert completed["payload"]["source"]["url"].endswith("BV1xx")
            assert completed["result"] == {"items": []}

            await connection.send(rpc_request(5, "task.list"))
            listed = (await receive_json(connection))["result"]
            assert [task["task_id"] for task in listed["tasks"]] == ["task-1"]
            assert listed["tasks"][0]["url"].endswith("BV1xx")
            assert "payload" not in listed["tasks"][0]
            assert listed["next_offset"] is None
    finally:
        await server.close()


def _snapshot_stub(task_id: str, created_at: datetime) -> TaskSnapshot[Any, Any]:
    return TaskSnapshot(
        task_id=task_id,
        state=TaskState.QUEUED,
        payload=cast("Any", None),
        result=None,
        error=None,
        created_at=created_at,
        started_at=None,
        finished_at=None,
        last_event_seq=0,
    )


def test_task_list_order_is_global_by_created_at_across_runtimes():
    # download 与 resolve 两个 runtime 的快照如按分块拼接，新任务会插入合并序列中段，
    # offset 分页会跨页漏掉/重复条目；task.list 的契约是按提交时间全局排序、并列时按 task_id 稳定
    download_early = _snapshot_stub("task-1", datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    resolve_mid = _snapshot_stub("resolve-1", datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC))
    download_late = _snapshot_stub("task-2", datetime(2026, 1, 1, 12, 0, 2, tzinfo=UTC))
    tie_a = _snapshot_stub("a-tie", datetime(2026, 1, 1, 12, 0, 3, tzinfo=UTC))
    tie_b = _snapshot_stub("b-tie", datetime(2026, 1, 1, 12, 0, 3, tzinfo=UTC))

    merged = sorted([download_late, tie_b, resolve_mid, tie_a, download_early], key=_task_snapshot_order)

    assert [snapshot.task_id for snapshot in merged] == ["task-1", "resolve-1", "task-2", "a-tie", "b-tie"]


def test_transport_rejects_non_loopback_hosts_and_empty_tokens():
    with pytest.raises(ValueError, match="loopback"):
        WebSocketServerOptions(token="secret", host="0.0.0.0")
    with pytest.raises(ValueError, match="token"):
        WebSocketServerOptions(token="")


@pytest.mark.processor
@as_sync
async def test_authentication_accepts_utf8_tokens():
    server, _, uri = await start_server(token="本地令牌")
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "本地令牌"}))
            assert (await receive_json(connection))["result"] == {"authenticated": True}
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_resolve_task_routing_reports_kind_across_endpoints():
    resolve = FakeResolveTaskApi(item_count=2)
    server, _, uri = await start_server(resolve_service=resolve)
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)

            await connection.send(
                rpc_request(2, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1r"}}})
            )
            started = (await receive_json(connection))["result"]
            assert started["task_id"] == "resolve-1"
            assert started["state"] == "queued"
            assert started["kind"] == "resolve"

            await connection.send(
                rpc_request(3, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV2r"}}})
            )
            assert (await receive_json(connection))["result"]["task_id"] == "resolve-2"

            await connection.send(
                rpc_request(
                    4, "download.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1d"}}}
                )
            )
            download_started = (await receive_json(connection))["result"]
            assert download_started["task_id"] == "task-1"
            assert download_started["kind"] == "download"

            await connection.send(rpc_request(5, "task.get", {"task_id": "resolve-2"}))
            assert (await receive_json(connection))["result"]["kind"] == "resolve"

            # 统一列表按提交时间全局排序，且每个条目都带 kind，供重连后的客户端判别任务类别
            await connection.send(rpc_request(6, "task.list"))
            listed = (await receive_json(connection))["result"]
            assert [(task["task_id"], task["kind"]) for task in listed["tasks"]] == [
                ("resolve-1", "resolve"),
                ("resolve-2", "resolve"),
                ("task-1", "download"),
            ]

            await connection.send(rpc_request(7, "task.cancel", {"task_id": "resolve-2"}))
            cancelled = (await receive_json(connection))["result"]
            assert cancelled["kind"] == "resolve"
            assert cancelled["state"] in {"cancelling", "cancelled"}

            await connection.send(rpc_request(8, "task.subscribe", {"task_id": "resolve-1", "after_seq": 0}))
            assert (await receive_json(connection))["result"]["task_id"] == "resolve-1"

            resolve.release.set()
            item_events: list[dict[str, Any]] = []
            async with asyncio.timeout(30):
                while True:
                    notification = await receive_json(connection)
                    if notification.get("method") != "task.event":
                        continue
                    params = notification["params"]
                    if params["kind"] == "item_listed":
                        item_events.append(params)
                    elif params["kind"] == "state" and params["state"] == "completed":
                        break
            assert [event["data"]["avid"] for event in item_events] == ["0", "1"]
            assert all(event["data"]["url"].startswith("https://example.com/") for event in item_events)
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_item_listed_burst_beyond_event_queue_is_fully_delivered():
    resolve = FakeResolveTaskApi(item_count=200)
    server, _, uri = await start_server(resolve_service=resolve)
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)
            await connection.send(
                rpc_request(2, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1b"}}})
            )
            await receive_json(connection)
            await connection.send(rpc_request(3, "task.subscribe", {"task_id": "resolve-1", "after_seq": 0}))
            await receive_json(connection)

            resolve.release.set()
            delivered = 0
            async with asyncio.timeout(30):
                while True:
                    notification = await receive_json(connection)
                    if notification.get("method") != "task.event":
                        continue
                    params = notification["params"]
                    if params["kind"] == "item_listed":
                        delivered += 1
                    elif params["kind"] == "state" and params["state"] == "completed":
                        break
            # 事件生产逐条让出控制权后，超过每连接发送队列（event_queue_size=128）的
            # 列表也能完整送达，而不是在第 129 条触发 slow-consumer 断连
            assert delivered == 200
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_simultaneously_completed_videos_stream_fully_over_websocket(monkeypatch: pytest.MonkeyPatch):
    _patch_batch_listing(monkeypatch)
    resolve = BatchStreamingResolveApi(video_count=200, pages_per_video=1)
    server, _, uri = await start_server(resolve_service=resolve)
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)
            await connection.send(
                rpc_request(2, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1s"}}})
            )
            await receive_json(connection)
            await connection.send(rpc_request(3, "task.subscribe", {"task_id": "resolve-1", "after_seq": 0}))
            await receive_json(connection)

            resolve.release.set()
            delivered = 0
            async with asyncio.timeout(30):
                while True:
                    notification = await receive_json(connection)
                    if notification.get("method") != "task.event":
                        continue
                    params = notification["params"]
                    if params["kind"] == "item_listed":
                        delivered += 1
                    elif params["kind"] == "state" and params["state"] == "completed":
                        break
            # 200 个视频同时就绪：单一 publisher 串行发布，事件不再在 sender 运行前灌满队列
            assert delivered == 200
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_single_video_with_more_pages_than_queue_streams_fully(monkeypatch: pytest.MonkeyPatch):
    _patch_batch_listing(monkeypatch)
    resolve = BatchStreamingResolveApi(video_count=1, pages_per_video=200)
    server, _, uri = await start_server(resolve_service=resolve)
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)
            await connection.send(
                rpc_request(2, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1p"}}})
            )
            await receive_json(connection)
            await connection.send(rpc_request(3, "task.subscribe", {"task_id": "resolve-1", "after_seq": 0}))
            await receive_json(connection)

            resolve.release.set()
            delivered = 0
            async with asyncio.timeout(30):
                while True:
                    notification = await receive_json(connection)
                    if notification.get("method") != "task.event":
                        continue
                    params = notification["params"]
                    if params["kind"] == "item_listed":
                        delivered += 1
                    elif params["kind"] == "state" and params["state"] == "completed":
                        break
            # 单视频 200 分 P（> event_queue_size=128）：逐分集让出使事件全部送达
            assert delivered == 200
    finally:
        await server.close()


@pytest.mark.processor
@as_sync
async def test_task_events_share_one_seq_space_across_runtimes():
    allocator = monotonic_seq_allocator()
    download_service = FakeDownloadTaskApi(seq_allocator=allocator)
    resolve = FakeResolveTaskApi(item_count=1, seq_allocator=allocator)
    server, _, uri = await start_server(service=download_service, resolve_service=resolve)
    try:
        async with connect(uri, proxy=None) as connection:
            await connection.send(rpc_request(1, "server.authenticate", {"token": "test-token"}))
            await receive_json(connection)

            await connection.send(
                rpc_request(
                    2, "download.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1d"}}}
                )
            )
            await receive_json(connection)
            await connection.send(
                rpc_request(3, "resolve.start", {"request": {"source": {"url": "https://www.bilibili.com/video/BV1r"}}})
            )
            await receive_json(connection)

            seen: dict[int, tuple[str, str, str]] = {}

            def record(event_json: dict[str, Any]) -> None:
                identity = (event_json["task_id"], event_json["kind"], json.dumps(event_json["data"], sort_keys=True))
                existing = seen.setdefault(event_json["seq"], identity)
                # v1 契约：客户端按 seq 去重 —— 同一 seq 只允许对应同一事件，
                # 绝不允许两个 runtime 的不同事件共用一个序号
                assert existing == identity

            for request_id, task_id in ((4, "task-1"), (5, "resolve-1")):
                await connection.send(rpc_request(request_id, "task.subscribe", {"task_id": task_id, "after_seq": 0}))
                replay = (await receive_json(connection))["result"]
                for event in replay["events"]:
                    record(event)

            download_service.release.set()
            resolve.release.set()
            completed: set[str] = set()
            async with asyncio.timeout(30):
                while completed < {"task-1", "resolve-1"}:
                    notification = await receive_json(connection)
                    if notification.get("method") != "task.event":
                        continue
                    params = notification["params"]
                    record(params)
                    if params["kind"] == "state" and params["state"] == "completed":
                        completed.add(params["task_id"])
            assert {task_id for _, (task_id, _, _) in seen.items()} == {"task-1", "resolve-1"}
    finally:
        await server.close()
