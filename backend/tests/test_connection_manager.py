import json
from typing import Any

import httpx
import pytest

from backend.src.connection_manager import (
    AutoCADPluginClient,
    AutoCADPluginHTTPError,
)


COMMAND = {
    "schema_version": "0.1",
    "command_id": "cmd-001",
    "application": "autocad",
    "operation": "create_line",
}

V02_COMMAND = {
    **COMMAND,
    "schema_version": "0.2",
    "run_id": "run-001",
    "import_id": None,
}


@pytest.mark.anyio
async def test_health_check_detects_loaded_plugin() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "application": "autocad",
                "plugin_version": "0.2.0",
                "supported_schema_versions": ["0.1", "0.2"],
            },
        )

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    assert await plugin.is_connected() is True
    health = await plugin.get_health()
    assert health is not None
    assert health["plugin_version"] == "0.2.0"


@pytest.mark.anyio
async def test_health_check_treats_request_failure_as_disconnected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    assert await plugin.is_connected() is False


@pytest.mark.anyio
async def test_command_is_posted_and_correlated() -> None:
    result = {
        "schema_version": "0.1",
        "command_id": "cmd-001",
        "status": "success",
        "message": "Line created successfully.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/command"
        assert json.loads(request.content) == COMMAND
        return httpx.Response(200, json=result)

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    assert await plugin.send_command(COMMAND) == result


@pytest.mark.anyio
async def test_plugin_http_error_remains_structured() -> None:
    error_body: dict[str, Any] = {
        "command_id": "cmd-001",
        "status": "error",
        "message": "AutoCAD has no active drawing.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=error_body)

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    with pytest.raises(AutoCADPluginHTTPError) as error:
        await plugin.send_command(COMMAND)

    assert error.value.status_code == 400
    assert error.value.body == error_body


@pytest.mark.anyio
async def test_mismatched_command_result_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "command_id": "different-command",
                "status": "success",
            },
        )

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ValueError, match="command_id did not match"):
        await plugin.send_command(COMMAND)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "different-run"),
        ("import_id", "different-import"),
    ],
)
async def test_mismatched_v02_lifecycle_identity_is_rejected(
    field: str,
    value: str,
) -> None:
    result = {
        "command_id": V02_COMMAND["command_id"],
        "run_id": V02_COMMAND["run_id"],
        "import_id": V02_COMMAND["import_id"],
        "status": "success",
    }
    result[field] = value

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=result)

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ValueError, match=rf"{field} did not match"):
        await plugin.send_command(V02_COMMAND)


@pytest.mark.anyio
async def test_command_timeout_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    plugin = AutoCADPluginClient(transport=httpx.MockTransport(handler))

    with pytest.raises(TimeoutError, match="did not return"):
        await plugin.send_command(COMMAND)
