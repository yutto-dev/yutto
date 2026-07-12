from __future__ import annotations

import asyncio
import hmac
import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import ValidationError
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

from yutto.__version__ import VERSION
from yutto.core.request import DownloadRequest
from yutto.runtime import TaskCapacityError
from yutto.server.rpc import JsonRpcDispatcher, JsonRpcError, encode_notification
from yutto.server.service import event_to_json, replay_to_json, snapshot_summary_to_json, snapshot_to_json

if TYPE_CHECKING:
    from collections.abc import Callable
    from socket import socket

    from yutto.runtime import EventReplay, TaskEvent, TaskSnapshot


AUTHENTICATION_ERROR = -32001
TASK_NOT_FOUND_ERROR = -32004
REQUEST_REJECTED_ERROR = -32010
SERVER_BUSY_ERROR = -32020


class DownloadTaskApi(Protocol):
    async def start(self) -> None: ...

    async def close(self, *, cancel_pending: bool = False) -> None: ...

    async def submit(self, request: DownloadRequest) -> TaskSnapshot[DownloadRequest, None]: ...

    def get(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None: ...

    def list(self) -> tuple[TaskSnapshot[DownloadRequest, None], ...]: ...

    async def cancel(self, task_id: str) -> TaskSnapshot[DownloadRequest, None] | None: ...

    def replay(self, task_id: str, *, after_seq: int = 0) -> EventReplay | None: ...

    def add_event_listener(self, listener: Callable[[TaskEvent], None]) -> Callable[[], None]: ...


@dataclass(frozen=True, slots=True)
class WebSocketServerOptions:
    token: str
    host: str = "127.0.0.1"
    port: int = 11223
    allowed_origins: tuple[str, ...] = ()
    authentication_timeout: float = 5.0
    event_queue_size: int = 128

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("server token must not be empty")
        if not _is_loopback_host(self.host):
            raise ValueError("yutto server may only listen on a loopback address")
        if not 0 <= self.port <= 65535:
            raise ValueError("server port must be between 0 and 65535")
        if self.authentication_timeout <= 0:
            raise ValueError("authentication timeout must be positive")
        if self.event_queue_size < 1:
            raise ValueError("event queue size must be at least 1")


class YuttoWebSocketServer:
    """Authenticated, local-only JSON-RPC transport for a download task service."""

    def __init__(
        self,
        task_service: DownloadTaskApi,
        options: WebSocketServerOptions,
        *,
        prepare_request: Callable[[DownloadRequest], DownloadRequest] | None = None,
        parse_request: Callable[[object], DownloadRequest] | None = None,
    ):
        self._task_service = task_service
        self.options = options
        self._token_bytes = options.token.encode("utf-8")
        self._prepare_request = prepare_request or (lambda request: request)
        self._parse_request = parse_request or DownloadRequest.model_validate
        self._server: Server | None = None

    @property
    def sockets(self) -> tuple[socket, ...]:
        if self._server is None or self._server.sockets is None:
            return ()
        return tuple(self._server.sockets)

    async def start(self) -> None:
        if self._server is not None:
            return
        await self._task_service.start()
        try:
            self._server = await serve(
                self._handle_connection,
                self.options.host,
                self.options.port,
                origins=[None, *(Origin(origin) for origin in self.options.allowed_origins)],
                compression=None,
                max_size=256 * 1024,
                max_queue=16,
                server_header="yutto",
            )
        except BaseException:
            await self._task_service.close(cancel_pending=True)
            raise

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        await self._server.serve_forever()

    async def close(self, *, cancel_pending: bool = True) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        await self._task_service.close(cancel_pending=cancel_pending)

    async def _handle_connection(self, connection: ServerConnection) -> None:
        authenticated = False
        authentication = JsonRpcDispatcher()

        @authentication.method("server.authenticate")
        async def authenticate(token: str) -> dict[str, bool]:
            nonlocal authenticated
            if not isinstance(token, str):
                raise JsonRpcError(-32602, "Invalid params")
            authenticated = hmac.compare_digest(token.encode("utf-8"), self._token_bytes)
            if not authenticated:
                raise JsonRpcError(AUTHENTICATION_ERROR, "Authentication failed")
            return {"authenticated": True}

        try:
            first_message = await asyncio.wait_for(
                connection.recv(),
                timeout=self.options.authentication_timeout,
            )
        except TimeoutError:
            await connection.close(code=1008, reason="authentication timeout")
            return
        except ConnectionClosed:
            return

        if not isinstance(first_message, str):
            await connection.close(code=1003, reason="text messages required")
            return

        response = await authentication.dispatch(first_message)
        if response is not None:
            await connection.send(response)
        if not authenticated:
            await connection.close(code=1008, reason="authentication required")
            return

        outgoing: asyncio.Queue[str] = asyncio.Queue(maxsize=self.options.event_queue_size)
        subscriptions: set[str] = set()
        sender = asyncio.create_task(self._send_messages(connection, outgoing), name="yutto-rpc-sender")
        dispatcher = self._create_dispatcher(subscriptions)

        def on_event(event: TaskEvent) -> None:
            if event.task_id not in subscriptions:
                return
            try:
                outgoing.put_nowait(encode_notification("task.event", event_to_json(event)))
            except asyncio.QueueFull:
                asyncio.create_task(connection.close(code=1013, reason="event consumer is too slow"))

        unsubscribe = self._task_service.add_event_listener(on_event)
        try:
            async for message in connection:
                if not isinstance(message, str):
                    await connection.close(code=1003, reason="text messages required")
                    break
                response = await dispatcher.dispatch(message)
                if response is not None:
                    try:
                        outgoing.put_nowait(response)
                    except asyncio.QueueFull:
                        await connection.close(code=1013, reason="event consumer is too slow")
                        break
        finally:
            unsubscribe()
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    def _create_dispatcher(self, subscriptions: set[str]) -> JsonRpcDispatcher:
        dispatcher = JsonRpcDispatcher()

        @dispatcher.method("server.info")
        async def server_info() -> dict[str, object]:
            return {
                "name": "yutto",
                "version": VERSION,
                "protocol_version": 1,
                "capabilities": [
                    "download.start",
                    "task.get",
                    "task.list",
                    "task.cancel",
                    "task.subscribe",
                    "task.unsubscribe",
                ],
            }

        @dispatcher.method("download.start")
        async def download_start(request: dict[str, object]) -> dict[str, object]:
            validated = self._parse_request(request)
            try:
                prepared = self._prepare_request(validated)
            except ValidationError:
                raise
            except ValueError as error:
                raise JsonRpcError(
                    REQUEST_REJECTED_ERROR,
                    "Request rejected",
                    {"reason": str(error)},
                ) from error
            try:
                snapshot = await self._task_service.submit(prepared)
            except TaskCapacityError as error:
                raise JsonRpcError(SERVER_BUSY_ERROR, "server task capacity reached") from error
            return snapshot_to_json(snapshot)

        @dispatcher.method("task.get")
        async def task_get(task_id: str) -> dict[str, object]:
            self._validate_task_id(task_id)
            return snapshot_to_json(self._require_task(task_id))

        @dispatcher.method("task.list")
        async def task_list(offset: int = 0, limit: int = 50) -> dict[str, object]:
            if (
                isinstance(offset, bool)
                or not isinstance(offset, int)
                or offset < 0
                or isinstance(limit, bool)
                or not isinstance(limit, int)
                or not 1 <= limit <= 100
            ):
                raise JsonRpcError(-32602, "Invalid params")
            snapshots = self._task_service.list()
            selected = snapshots[offset : offset + limit]
            next_offset = offset + len(selected)
            return {
                "tasks": [snapshot_summary_to_json(snapshot) for snapshot in selected],
                "offset": offset,
                "next_offset": next_offset if next_offset < len(snapshots) else None,
                "total": len(snapshots),
            }

        @dispatcher.method("task.cancel")
        async def task_cancel(task_id: str) -> dict[str, object]:
            self._validate_task_id(task_id)
            snapshot = await self._task_service.cancel(task_id)
            if snapshot is None:
                raise JsonRpcError(TASK_NOT_FOUND_ERROR, "Task not found")
            return snapshot_to_json(snapshot)

        @dispatcher.method("task.subscribe")
        async def task_subscribe(task_id: str, after_seq: int = 0) -> dict[str, object]:
            self._validate_task_id(task_id)
            if isinstance(after_seq, bool) or not isinstance(after_seq, int):
                raise JsonRpcError(-32602, "Invalid params")
            subscriptions.add(task_id)
            try:
                replay = self._task_service.replay(task_id, after_seq=after_seq)
            except ValueError as error:
                subscriptions.discard(task_id)
                raise JsonRpcError(-32602, "Invalid params", {"reason": str(error)}) from error
            if replay is None:
                subscriptions.discard(task_id)
                raise JsonRpcError(TASK_NOT_FOUND_ERROR, "Task not found")
            return replay_to_json(replay)

        @dispatcher.method("task.unsubscribe")
        async def task_unsubscribe(task_id: str) -> dict[str, bool]:
            self._validate_task_id(task_id)
            subscribed = task_id in subscriptions
            subscriptions.discard(task_id)
            return {"subscribed": subscribed}

        return dispatcher

    def _require_task(self, task_id: str) -> TaskSnapshot[DownloadRequest, None]:
        snapshot = self._task_service.get(task_id)
        if snapshot is None:
            raise JsonRpcError(TASK_NOT_FOUND_ERROR, "Task not found")
        return snapshot

    @staticmethod
    def _validate_task_id(task_id: object) -> None:
        if not isinstance(task_id, str) or not task_id:
            raise JsonRpcError(-32602, "Invalid params")

    @staticmethod
    async def _send_messages(connection: ServerConnection, outgoing: asyncio.Queue[str]) -> None:
        while True:
            message = await outgoing.get()
            try:
                await connection.send(message)
            finally:
                outgoing.task_done()


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
