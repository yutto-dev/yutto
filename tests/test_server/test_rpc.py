from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import BaseModel

from yutto.server import JsonRpcDispatcher, JsonRpcError, encode_notification
from yutto.utils.functional import as_sync

pytestmark = pytest.mark.processor


def decode(response: str | None) -> dict[str, object]:
    assert response is not None
    return cast("dict[str, object]", json.loads(response))


def error(code: int, message: str, request_id: object = None) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


@as_sync
async def test_dispatches_positional_and_named_params_and_echoes_ids():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("subtract")
    async def subtract(minuend: int, subtrahend: int) -> int:
        return minuend - subtrahend

    assert decode(await dispatcher.dispatch('{"jsonrpc":"2.0","method":"subtract","params":[42,23],"id":1}')) == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": 19,
    }
    assert decode(
        await dispatcher.dispatch(
            '{"jsonrpc":"2.0","method":"subtract","params":{"subtrahend":23,"minuend":42},"id":"job-1"}'
        )
    ) == {"jsonrpc": "2.0", "id": "job-1", "result": 19}


@as_sync
async def test_explicit_null_id_is_a_request_but_missing_id_is_a_notification():
    dispatcher = JsonRpcDispatcher()
    calls: list[str] = []

    @dispatcher.method("record")
    async def record(value: str) -> bool:
        calls.append(value)
        return True

    response = await dispatcher.dispatch('{"jsonrpc":"2.0","method":"record","params":{"value":"request"},"id":null}')
    notification_response = await dispatcher.dispatch(
        '{"jsonrpc":"2.0","method":"record","params":{"value":"notification"}}'
    )

    assert decode(response) == {"jsonrpc": "2.0", "id": None, "result": True}
    assert notification_response is None
    assert calls == ["request", "notification"]


@pytest.mark.parametrize("message", ["{", '{"jsonrpc":"2.0"} trailing', "NaN"])
@as_sync
async def test_parse_error(message: str):
    dispatcher = JsonRpcDispatcher()

    assert decode(await dispatcher.dispatch(message)) == error(-32700, "Parse error")


@pytest.mark.parametrize(
    "message",
    [
        "[]",
        '"request"',
        '{"jsonrpc":"1.0","method":"ping","id":"kept-out"}',
        '{"jsonrpc":"2.0","id":1}',
        '{"jsonrpc":"2.0","method":1,"id":1}',
        '{"jsonrpc":"2.0","method":"ping","id":true}',
        '{"jsonrpc":"2.0","method":"ping","id":{}}',
    ],
)
@as_sync
async def test_invalid_request_rejects_non_object_batches_and_invalid_members(message: str):
    dispatcher = JsonRpcDispatcher()

    assert decode(await dispatcher.dispatch(message)) == error(-32600, "Invalid Request")


@as_sync
async def test_method_not_found_preserves_request_id():
    dispatcher = JsonRpcDispatcher()

    response = await dispatcher.dispatch('{"jsonrpc":"2.0","method":"missing","id":"request-7"}')

    assert decode(response) == error(-32601, "Method not found", "request-7")


@as_sync
async def test_invalid_params_covers_shape_and_signature_binding_errors():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("add")
    async def add(left: int, right: int) -> int:
        return left + right

    invalid_messages = [
        '{"jsonrpc":"2.0","method":"add","params":"not-structured","id":1}',
        '{"jsonrpc":"2.0","method":"add","params":[1],"id":2}',
        '{"jsonrpc":"2.0","method":"add","params":{"left":1,"right":2,"extra":3},"id":3}',
    ]

    for request_id, message in enumerate(invalid_messages, start=1):
        assert decode(await dispatcher.dispatch(message)) == error(-32602, "Invalid params", request_id)


@as_sync
async def test_pydantic_validation_error_is_invalid_params():
    class PositiveParams(BaseModel):
        value: int

    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("validate")
    async def validate(value: object) -> int:
        return PositiveParams.model_validate({"value": value}).value

    response = await dispatcher.dispatch('{"jsonrpc":"2.0","method":"validate","params":{"value":"not-an-int"},"id":9}')

    assert decode(response) == error(-32602, "Invalid params", 9)


@as_sync
async def test_handler_exception_and_unserializable_result_are_internal_errors():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("explode")
    async def explode() -> None:
        raise RuntimeError("must not leak")

    @dispatcher.method("opaque")
    async def opaque() -> object:
        return object()

    assert decode(await dispatcher.dispatch('{"jsonrpc":"2.0","method":"explode","id":1}')) == error(
        -32603, "Internal error", 1
    )
    assert decode(await dispatcher.dispatch('{"jsonrpc":"2.0","method":"opaque","id":2}')) == error(
        -32603, "Internal error", 2
    )


@as_sync
async def test_json_rpc_error_exposes_custom_code_message_and_optional_data():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("busy")
    async def busy() -> None:
        raise JsonRpcError(-32001, "Task is busy", {"retry_after": 3})

    @dispatcher.method("unavailable")
    async def unavailable() -> None:
        raise JsonRpcError(-32002, "Task is unavailable")

    assert decode(await dispatcher.dispatch('{"jsonrpc":"2.0","method":"busy","id":"busy-1"}')) == {
        "jsonrpc": "2.0",
        "id": "busy-1",
        "error": {"code": -32001, "message": "Task is busy", "data": {"retry_after": 3}},
    }
    assert decode(await dispatcher.dispatch('{"jsonrpc":"2.0","method":"unavailable","id":4}')) == error(
        -32002, "Task is unavailable", 4
    )


@as_sync
async def test_unserializable_json_rpc_error_data_becomes_internal_error():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("broken-error")
    async def broken_error() -> None:
        raise JsonRpcError(-32001, "Broken", object())

    response = await dispatcher.dispatch('{"jsonrpc":"2.0","method":"broken-error","id":5}')

    assert decode(response) == error(-32603, "Internal error", 5)


@as_sync
async def test_notifications_never_produce_responses_even_on_errors():
    dispatcher = JsonRpcDispatcher()

    @dispatcher.method("needs-value")
    async def needs_value(value: int) -> int:
        return value

    @dispatcher.method("explode")
    async def explode() -> None:
        raise RuntimeError

    @dispatcher.method("expected-error")
    async def expected_error() -> None:
        raise JsonRpcError(-32001, "Expected")

    messages = [
        '{"jsonrpc":"2.0","method":"missing"}',
        '{"jsonrpc":"2.0","method":"needs-value","params":[]}',
        '{"jsonrpc":"2.0","method":"explode"}',
        '{"jsonrpc":"2.0","method":"expected-error"}',
    ]

    for message in messages:
        assert await dispatcher.dispatch(message) is None


def test_registration_rejects_sync_and_duplicate_methods():
    dispatcher = JsonRpcDispatcher()

    async def async_handler() -> None:
        pass

    def sync_handler() -> None:
        pass

    dispatcher.register("method", async_handler)

    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register("method", async_handler)
    with pytest.raises(TypeError, match="must be async"):
        dispatcher.register("sync", sync_handler)  # ty: ignore[invalid-argument-type]


def test_encode_notification_supports_named_and_positional_params():
    named = decode(encode_notification("task.event", {"task_id": "task-1", "seq": 7}))
    positional = decode(encode_notification("server.ready", ["v1"]))

    assert named == {
        "jsonrpc": "2.0",
        "method": "task.event",
        "params": {"task_id": "task-1", "seq": 7},
    }
    assert positional == {"jsonrpc": "2.0", "method": "server.ready", "params": ["v1"]}
    assert "id" not in named
    assert "id" not in positional


def test_json_rpc_error_and_notification_validate_protocol_members():
    with pytest.raises(TypeError, match="code must be an integer"):
        JsonRpcError(True, "invalid")
    with pytest.raises(TypeError, match="message must be a string"):
        JsonRpcError(-32000, 1)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="method must be a string"):
        encode_notification(1, {})  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="params must be an object or array"):
        encode_notification("task.event", "invalid")  # ty: ignore[invalid-argument-type]
