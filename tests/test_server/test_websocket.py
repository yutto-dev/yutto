from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.typing import Origin

from yutto.core.request import DownloadRequest
from yutto.runtime import TaskContext, TaskRuntime
from yutto.server.websocket import WebSocketServerOptions, YuttoWebSocketServer
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor

if TYPE_CHECKING:
    from collections.abc import Callable

    from yutto.runtime import EventReplay, TaskEvent, TaskSnapshot


class FakeDownloadTaskApi:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.runtime = TaskRuntime[DownloadRequest, None](
            self._run,
            task_id_factory=lambda: "task-1",
        )

    async def start(self) -> None:
        await self.runtime.start()

    async def close(self, *, cancel_pending: bool = False) -> None:
        await self.runtime.close(cancel_pending=cancel_pending)

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, None]:
        return await self.runtime.submit(request)

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None:
        return self.runtime.get(task_id)

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, None], ...]:
        return self.runtime.list()

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None:
        return await self.runtime.cancel(task_id)

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None:
        return self.runtime.replay(task_id, after_seq=after_seq)

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]:
        return self.runtime.add_event_listener(listener)

    async def _run(self, request: DownloadRequest, context: TaskContext) -> None:
        await self.release.wait()
        context.emit("progress", {"current": 1, "total": 1})


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
) -> tuple[YuttoWebSocketServer, FakeDownloadTaskApi, str]:
    service = FakeDownloadTaskApi()
    server = YuttoWebSocketServer(
        service,
        WebSocketServerOptions(
            token=token,
            host="127.0.0.1",
            port=0,
            allowed_origins=allowed_origins,
        ),
    )
    await server.start()
    port = server.sockets[0].getsockname()[1]
    return server, service, f"ws://127.0.0.1:{port}"


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

            await connection.send(rpc_request(5, "task.list"))
            listed = (await receive_json(connection))["result"]
            assert [task["task_id"] for task in listed["tasks"]] == ["task-1"]
            assert "payload" not in listed["tasks"][0]
            assert listed["next_offset"] is None
    finally:
        await server.close()


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
