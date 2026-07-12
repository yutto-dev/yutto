from __future__ import annotations

import inspect
import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from pydantic import ValidationError

RpcMethod: TypeAlias = Callable[..., Awaitable[object]]

_PARSE_ERROR = (-32700, "Parse error")
_INVALID_REQUEST = (-32600, "Invalid Request")
_METHOD_NOT_FOUND = (-32601, "Method not found")
_INVALID_PARAMS = (-32602, "Invalid params")
_INTERNAL_ERROR = (-32603, "Internal error")
_NO_PARAMS = object()


class JsonRpcError(Exception):
    """An error that a registered method intentionally exposes to its caller."""

    def __init__(self, code: int, message: str, data: object | None = None) -> None:
        if isinstance(code, bool) or not isinstance(code, int):
            raise TypeError("JSON-RPC error code must be an integer")
        if not isinstance(message, str):
            raise TypeError("JSON-RPC error message must be a string")

        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True, slots=True)
class _RegisteredMethod:
    handler: RpcMethod
    signature: inspect.Signature


class JsonRpcDispatcher:
    """Dispatch one JSON-RPC 2.0 request or notification per text message."""

    def __init__(self) -> None:
        self._methods: dict[str, _RegisteredMethod] = {}

    def register(self, name: str, handler: RpcMethod) -> RpcMethod:
        """Register an async method and return it unchanged."""
        if not isinstance(name, str):
            raise TypeError("method name must be a string")
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("JSON-RPC methods must be async functions")
        if name in self._methods:
            raise ValueError(f"method is already registered: {name}")

        try:
            method_signature = inspect.signature(handler)
        except (TypeError, ValueError) as exc:
            raise TypeError("JSON-RPC methods must expose a callable signature") from exc

        self._methods[name] = _RegisteredMethod(handler, method_signature)
        return handler

    def method(self, name: str) -> Callable[[RpcMethod], RpcMethod]:
        """Return a decorator that registers an async method under ``name``."""

        def decorator(handler: RpcMethod) -> RpcMethod:
            return self.register(name, handler)

        return decorator

    async def dispatch(self, message: str) -> str | None:
        """Dispatch a text message, returning a response or ``None`` for notifications."""
        try:
            payload = json.loads(message, parse_constant=_reject_non_json_number)
        except (json.JSONDecodeError, ValueError):
            return _error_response(None, _PARSE_ERROR)

        if not isinstance(payload, dict):
            return _error_response(None, _INVALID_REQUEST)

        request = cast("dict[str, Any]", payload)
        has_id = "id" in request
        request_id = request.get("id")

        if (
            request.get("jsonrpc") != "2.0"
            or not isinstance(request.get("method"), str)
            or (has_id and not _is_valid_request_id(request_id))
        ):
            return _error_response(None, _INVALID_REQUEST)

        params = request.get("params", _NO_PARAMS)
        if params is not _NO_PARAMS and not isinstance(params, (dict, list)):
            return None if not has_id else _error_response(request_id, _INVALID_PARAMS)

        registered = self._methods.get(request["method"])
        if registered is None:
            return None if not has_id else _error_response(request_id, _METHOD_NOT_FOUND)

        if params is _NO_PARAMS:
            args: tuple[object, ...] = ()
            kwargs: dict[str, object] = {}
        elif isinstance(params, list):
            args = tuple(params)
            kwargs = {}
        else:
            args = ()
            kwargs = params

        try:
            registered.signature.bind(*args, **kwargs)
        except TypeError:
            return None if not has_id else _error_response(request_id, _INVALID_PARAMS)

        try:
            result = await registered.handler(*args, **kwargs)
        except JsonRpcError as exc:
            if not has_id:
                return None
            try:
                return _error_response(request_id, (exc.code, exc.message), data=exc.data)
            except (TypeError, ValueError):
                return _error_response(request_id, _INTERNAL_ERROR)
        except ValidationError:
            return None if not has_id else _error_response(request_id, _INVALID_PARAMS)
        except Exception:
            return None if not has_id else _error_response(request_id, _INTERNAL_ERROR)

        if not has_id:
            return None

        try:
            return _encode({"jsonrpc": "2.0", "id": request_id, "result": result})
        except (TypeError, ValueError):
            return _error_response(request_id, _INTERNAL_ERROR)


def encode_notification(method: str, params: list[object] | dict[str, object]) -> str:
    """Encode a JSON-RPC 2.0 notification without a request ID."""
    if not isinstance(method, str):
        raise TypeError("notification method must be a string")
    if not isinstance(params, (dict, list)):
        raise TypeError("notification params must be an object or array")
    return _encode({"jsonrpc": "2.0", "method": method, "params": params})


def _is_valid_request_id(value: object) -> bool:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _reject_non_json_number(value: str) -> None:
    raise ValueError(f"not a JSON number: {value}")


def _error_response(request_id: object, error: tuple[int, str], *, data: object | None = None) -> str:
    code, message = error
    error_payload: dict[str, object] = {"code": code, "message": message}
    if data is not None:
        error_payload["data"] = data
    return _encode(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error_payload,
        }
    )


def _encode(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
