import copy
import sys
from pathlib import Path

from fastapi.testclient import TestClient


# Ensure the repository root is available for imports.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.src.api import app  # noqa: E402


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


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"
    assert body["service"] == "AutoCAD-AI mock bridge"


def test_valid_create_line_command() -> None:
    response = client.post(
        "/commands",
        json=VALID_CREATE_LINE_COMMAND,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "success"
    assert body["command_id"] == "cmd-test-001"
    assert body["data"]["mock_mode"] is True
    assert body["data"]["drawing_units"] == "inches"
    assert body["data"]["layer"] == "AI-WALL"

    # Twenty feet should become 240 inches.
    assert body["data"]["end_in_drawing_units"] == [
        240.0,
        0.0,
        0.0,
    ]


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