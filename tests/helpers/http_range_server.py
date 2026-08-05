from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import InitVar, dataclass, field
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType
    from typing import Self


_RANGE_PATTERN = re.compile(r"bytes=(\d+)-(\d*)")


class RangeFault(StrEnum):
    NONE = "none"
    IGNORE = "ignore"
    TRUNCATE = "truncate"
    WRONG_CONTENT_RANGE = "wrong-content-range"


RangeBounds = tuple[int, int]
RangeFaultSpec = tuple[RangeBounds, RangeFault]


@dataclass(frozen=True, slots=True)
class RecordedRangeRequest:
    path: str
    range_header: str | None


@dataclass
class LocalRangeServer:
    """Threaded localhost Range server with deterministic one-shot faults."""

    payload: bytes
    faults: InitVar[Iterable[RangeFaultSpec] | None] = None
    delays: dict[RangeBounds, float] = field(default_factory=dict)
    release_after: dict[RangeBounds, RangeBounds] = field(default_factory=dict)
    barrier_timeout: float = 2
    requests: list[RecordedRangeRequest] = field(default_factory=list, init=False)
    completed_requests: list[RecordedRangeRequest] = field(default_factory=list, init=False)
    _faults: dict[RangeBounds, deque[RangeFault]] = field(default_factory=dict, init=False)
    _completed_ranges: dict[RangeBounds, Event] = field(default_factory=dict, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)
    _server: ThreadingHTTPServer | None = field(default=None, init=False)
    _thread: Thread | None = field(default=None, init=False)

    def __post_init__(self, faults: Iterable[RangeFaultSpec] | None) -> None:
        for expected_range, fault in faults or ():
            self._faults.setdefault(expected_range, deque()).append(fault)

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("range server is not running")
        return f"http://127.0.0.1:{self._server.server_port}/media"

    def __enter__(self) -> Self:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                completed_range = owner._serve(self)
                request = RecordedRangeRequest(self.path, self.headers.get("Range"))
                with owner._lock:
                    owner.completed_requests.append(request)
                    completed_event = (
                        owner._completed_ranges.setdefault(completed_range, Event())
                        if completed_range is not None
                        else None
                    )
                if completed_event is not None:
                    completed_event.set()

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        assert self._server is not None
        assert self._thread is not None
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        self._server = None
        self._thread = None

    def _serve(self, handler: BaseHTTPRequestHandler) -> RangeBounds | None:
        range_header = handler.headers.get("Range")
        with self._lock:
            self.requests.append(RecordedRangeRequest(handler.path, range_header))

        if range_header is None:
            self._write_response(handler, 200, self.payload)
            return None

        match = _RANGE_PATTERN.fullmatch(range_header)
        if match is None:
            self._write_response(handler, 416, b"", content_range=f"bytes */{len(self.payload)}")
            return None

        start = int(match.group(1))
        requested_end = int(match.group(2)) if match.group(2) else len(self.payload) - 1
        end = min(requested_end, len(self.payload) - 1)
        if start >= len(self.payload) or start > end:
            self._write_response(handler, 416, b"", content_range=f"bytes */{len(self.payload)}")
            return None

        requested_range = (start, end)
        with self._lock:
            faults = self._faults.get(requested_range)
            fault = faults.popleft() if faults else RangeFault.NONE
            if faults is not None and not faults:
                del self._faults[requested_range]

        if dependency := self.release_after.get(requested_range):
            with self._lock:
                dependency_completed = self._completed_ranges.setdefault(dependency, Event())
            if not dependency_completed.wait(self.barrier_timeout):
                self._write_response(handler, 500, b"range barrier timed out")
                return None

        if fault is RangeFault.IGNORE:
            self._write_response(handler, 200, self.payload)
            return requested_range

        if delay := self.delays.get((start, end)):
            time.sleep(delay)

        body = self.payload[start : end + 1]
        if fault is RangeFault.TRUNCATE and body:
            body = body[:-1]
        content_start = start + 1 if fault is RangeFault.WRONG_CONTENT_RANGE else start
        self._write_response(
            handler,
            206,
            body,
            content_range=f"bytes {content_start}-{end}/{len(self.payload)}",
        )
        return requested_range

    @staticmethod
    def _write_response(
        handler: BaseHTTPRequestHandler,
        status: int,
        body: bytes,
        *,
        content_range: str | None = None,
    ) -> None:
        handler.close_connection = True
        handler.send_response(status)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Connection", "close")
        if content_range is not None:
            handler.send_header("Content-Range", content_range)
        handler.end_headers()
        handler.wfile.write(body)
