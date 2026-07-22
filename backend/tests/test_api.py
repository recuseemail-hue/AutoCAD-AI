import asyncio
import copy
import sys
from pathlib import Path

from fastapi.testclient import TestClient


# Ensure the repository root is available for imports.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.src.api import app  # noqa: E402
from backend.src.connection_manager import AutoCADConnectionManager  # noqa: E402


client = TestClient(app)


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

SUCCESSFUL_COMMAND_RESULT = {
    "message_type": "command_result",
    "command_id": "cmd-test-001",
    "application": "autocad",
    "status": "succeeded",
    "result": {
        "document": "TestDrawing.dwg",
        "created_entities": [
            {
                "type": "line",
                "handle": "TEST-001",
                "layer": "AI-WALL",
            }
        ],
    },
    "warnings": [],
    "error": None,
}


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"
    assert body["service"] == "AutoCAD-AI bridge"


def test_valid_create_line_command(monkeypatch) -> None:
    async def send_command(command: dict) -> dict:
        assert command == VALID_CREATE_LINE_COMMAND
        return SUCCESSFUL_COMMAND_RESULT

    monkeypatch.setattr(
        "backend.src.api.autocad_connection_manager.is_connected",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.src.api.autocad_connection_manager.send_command",
        send_command,
    )

    response = client.post(
        "/commands",
        json=VALID_CREATE_LINE_COMMAND,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "succeeded"
    assert body["command_id"] == "cmd-test-001"
    assert body["result"]["document"] == "TestDrawing.dwg"


def test_connection_manager_correlates_command_result() -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.sent_messages: list[dict] = []

        async def send_json(self, message: dict) -> None:
            self.sent_messages.append(message)

    async def exercise_manager() -> None:
        manager = AutoCADConnectionManager()
        websocket = FakeWebSocket()
        manager.connection = websocket  # type: ignore[assignment]

        response_task = asyncio.create_task(
            manager.send_command(
                VALID_CREATE_LINE_COMMAND,
                timeout_seconds=1,
            )
        )

        await asyncio.sleep(0)

        assert websocket.sent_messages == [VALID_CREATE_LINE_COMMAND]
        assert manager.resolve_command(SUCCESSFUL_COMMAND_RESULT) is True
        assert await response_task == SUCCESSFUL_COMMAND_RESULT
        assert manager.pending_commands == {}

    asyncio.run(exercise_manager())


def test_command_is_rejected_when_autocad_is_disconnected() -> None:
    response = client.post(
        "/commands",
        json=VALID_CREATE_LINE_COMMAND,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AutoCAD is not connected."


def test_invalid_command_is_rejected() -> None:
    invalid_command = copy.deepcopy(
        VALID_CREATE_LINE_COMMAND
    )

    del invalid_command["parameters"]["end"]

    response = client.post(
        "/commands",
        json=invalid_command,
    )

    assert response.status_code == 422

    body = response.json()

    assert "Invalid command" in body["detail"]
    assert "end" in body["detail"]
