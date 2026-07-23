import copy
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


# Ensure the repository root is available for imports.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.src import api  # noqa: E402
from backend.src.connection_manager import AutoCADPluginHTTPError  # noqa: E402


client = TestClient(api.app)


VALID_CREATE_LINE_COMMAND = {
    "schema_version": "0.1",
    "command_id": "cmd-test-001",
    "application": "autocad",
    "operation": "create_line",
    "parameters": {
        "start": {
            "x": 0,
            "y": 0,
            "z": 0,
        },
        "end": {
            "x": 20,
            "y": 0,
            "z": 0,
        },
        "layer": "AI-WALL",
        "create_layer_if_missing": True,
    },
    "units": "feet",
    "coordinate_system": "world",
    "requires_approval": False,
}

SUCCESSFUL_PLUGIN_RESULT = {
    "schema_version": "0.1",
    "command_id": "cmd-test-001",
    "status": "success",
    "message": "Line created successfully.",
    "affected_objects": [
        {
            "object_type": "LINE",
            "object_id": "2AF",
            "action": "created",
        }
    ],
    "data": {
        "layer": "AI-WALL",
        "start_in_drawing_units": [0.0, 0.0, 0.0],
        "end_in_drawing_units": [240.0, 0.0, 0.0],
    },
    "undo_token": "ai-action-test-001",
    "warnings": [],
}


def set_plugin_connection(
    monkeypatch: pytest.MonkeyPatch,
    connected: bool,
) -> None:
    async def fake_is_connected() -> bool:
        return connected

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        fake_is_connected,
    )


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AutoCAD-AI bridge",
    }


def test_application_status_reports_plugin_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_plugin_connection(monkeypatch, connected=True)

    response = client.get("/applications")

    assert response.status_code == 200
    assert response.json() == {"autocad": {"connected": True}}


def test_valid_create_line_command_returns_real_plugin_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        assert command == VALID_CREATE_LINE_COMMAND
        return SUCCESSFUL_PLUGIN_RESULT

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=VALID_CREATE_LINE_COMMAND)

    assert response.status_code == 200
    assert response.json() == SUCCESSFUL_PLUGIN_RESULT


def test_disconnected_plugin_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_plugin_connection(monkeypatch, connected=False)

    response = client.post("/commands", json=VALID_CREATE_LINE_COMMAND)

    assert response.status_code == 503
    assert response.json()["detail"] == "AutoCAD is not connected."


def test_plugin_error_status_and_body_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_plugin_connection(monkeypatch, connected=True)
    plugin_error = {
        "schema_version": "0.1",
        "command_id": "cmd-test-001",
        "status": "error",
        "message": "The requested layer is unavailable.",
        "affected_objects": [],
        "warnings": [],
    }

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        raise AutoCADPluginHTTPError(400, plugin_error)

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=VALID_CREATE_LINE_COMMAND)

    assert response.status_code == 400
    assert response.json()["detail"] == plugin_error


def test_plugin_timeout_returns_504(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        raise TimeoutError("The AutoCAD plugin did not return a command result in time.")

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=VALID_CREATE_LINE_COMMAND)

    assert response.status_code == 504
    assert "did not return" in response.json()["detail"]


def test_invalid_command_is_rejected_before_plugin_health_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_health_check() -> bool:
        raise AssertionError("Invalid commands must not reach the plugin.")

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        unexpected_health_check,
    )
    invalid_command = copy.deepcopy(VALID_CREATE_LINE_COMMAND)
    del invalid_command["parameters"]["end"]

    response = client.post("/commands", json=invalid_command)

    assert response.status_code == 422
    assert "Invalid command" in response.json()["detail"]
    assert "end" in response.json()["detail"]


def test_units_unsupported_by_plugin_are_rejected_by_schema() -> None:
    invalid_command = copy.deepcopy(VALID_CREATE_LINE_COMMAND)
    invalid_command["units"] = "drawing_units"

    response = client.post("/commands", json=invalid_command)

    assert response.status_code == 422
    assert "drawing_units" in response.json()["detail"]
