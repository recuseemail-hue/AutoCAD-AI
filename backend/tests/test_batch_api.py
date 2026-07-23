import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.src import api
from backend.src.config import BRIDGE_VERSION, PROJECT_ROOT
from backend.src.connection_manager import AutoCADPluginHTTPError
from backend.src.contracts import validate_result
from backend.src.observability import COMMAND_LOGGER_NAME


client = TestClient(api.app)
REQUESTS = PROJECT_ROOT / "examples" / "requests"
RESPONSES = PROJECT_ROOT / "examples" / "responses"


def load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def raw_plugin_result(normalized_fixture: str) -> dict:
    result = load_fixture(RESPONSES / normalized_fixture)
    versions = result.pop("versions")
    timestamps = result.pop("timestamps")
    result["plugin_version"] = versions["plugin"]
    result["completed_at"] = timestamps["completed_at"]
    return result


def set_plugin_connection(
    monkeypatch: pytest.MonkeyPatch,
    connected: bool,
) -> None:
    async def fake_is_connected() -> bool:
        return connected

    async def fake_get_health() -> dict[str, Any] | None:
        if not connected:
            return None
        return {
            "status": "ok",
            "application": "autocad",
            "plugin_version": "0.4.0",
            "supported_schema_versions": ["0.1", "0.2", "0.3", "0.4"],
        }

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        fake_is_connected,
    )
    monkeypatch.setattr(
        api.autocad_plugin_client,
        "get_health",
        fake_get_health,
    )


@pytest.mark.parametrize(
    ("request_fixture", "result_fixture", "validate_only"),
    [
        (
            "validate-batch-v0.4.json",
            "validate-batch-success-v0.4.json",
            True,
        ),
        (
            "execute-batch-v0.4.json",
            "execute-batch-success-v0.4.json",
            False,
        ),
    ],
)
def test_v04_batch_success_is_normalized_and_correlated(
    monkeypatch: pytest.MonkeyPatch,
    request_fixture: str,
    result_fixture: str,
    validate_only: bool,
) -> None:
    command = load_fixture(REQUESTS / request_fixture)
    plugin_result = raw_plugin_result(result_fixture)
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(received: dict[str, Any]) -> dict[str, Any]:
        assert received == command
        return plugin_result

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 200
    body = response.json()
    validate_result(body)
    assert body["schema_version"] == "0.4"
    assert body["run_id"] == command["run_id"]
    assert body["import_id"] == command["import_id"]
    assert body["command_id"] == command["command_id"]
    assert body["data"]["validate_only"] is validate_only
    assert body["versions"] == {
        "bridge": BRIDGE_VERSION,
        "plugin": "0.4.0",
    }


def test_v04_disconnected_error_is_structured_and_correlated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    set_plugin_connection(monkeypatch, connected=False)

    response = client.post("/commands", json=command)

    assert response.status_code == 503
    body = response.json()
    assert body["schema_version"] == "0.4"
    assert body["run_id"] == command["run_id"]
    assert body["import_id"] == command["import_id"]
    assert body["command_id"] == command["command_id"]
    assert body["error"]["code"] == "AUTOCAD_DISCONNECTED"


def test_v04_rejects_connected_older_plugin_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")

    async def fake_is_connected() -> bool:
        return True

    async def fake_get_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "application": "autocad",
            "plugin_version": "0.3.0",
            "supported_schema_versions": ["0.1", "0.2", "0.3"],
        }

    async def unexpected_send(command: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("Unsupported commands must not reach the plugin.")

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        fake_is_connected,
    )
    monkeypatch.setattr(
        api.autocad_plugin_client,
        "get_health",
        fake_get_health,
    )
    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        unexpected_send,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PLUGIN_SCHEMA_UNSUPPORTED"
    assert body["error"]["details"] == {
        "plugin_version": "0.3.0",
        "supported_schema_versions": ["0.1", "0.2", "0.3"],
    }


def test_v04_handles_disconnect_during_version_negotiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")

    async def fake_is_connected() -> bool:
        return True

    async def fake_get_health() -> None:
        return None

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        fake_is_connected,
    )
    monkeypatch.setattr(
        api.autocad_plugin_client,
        "get_health",
        fake_get_health,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTOCAD_DISCONNECTED"


@pytest.mark.parametrize(
    ("fixture_name", "status_code", "error_code"),
    [
        (
            "execute-batch-document-mismatch-v0.4.json",
            409,
            "DOCUMENT_MISMATCH",
        ),
        (
            "execute-batch-rollback-v0.4.json",
            500,
            "BATCH_ROLLED_BACK",
        ),
    ],
)
def test_v04_plugin_errors_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
    fixture_name: str,
    status_code: int,
    error_code: str,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    plugin_error = raw_plugin_result(fixture_name)
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        raise AutoCADPluginHTTPError(status_code, plugin_error)

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == status_code
    body = response.json()
    validate_result(body)
    assert body["status"] == "error"
    assert body["error"]["code"] == error_code
    assert body["affected_objects"] == []
    assert body["undo_token"] is None


def test_v04_duplicate_command_error_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    plugin_error = raw_plugin_result(
        "execute-batch-document-mismatch-v0.4.json"
    )
    plugin_error["document"] = {
        "name": "Drawing1.dwg",
        "fingerprint_guid": "11111111-1111-1111-1111-111111111111",
    }
    plugin_error["message"] = "This command_id was already executed."
    plugin_error["error"] = {
        "code": "DUPLICATE_COMMAND",
        "message": "This command_id was already executed.",
        "details": None,
    }
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        raise AutoCADPluginHTTPError(409, plugin_error)

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_COMMAND"


def test_v04_retry_returns_duplicate_without_second_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    plugin_success = raw_plugin_result(
        "execute-batch-success-v0.4.json"
    )
    plugin_duplicate = raw_plugin_result(
        "execute-batch-document-mismatch-v0.4.json"
    )
    plugin_duplicate["document"] = plugin_success["document"]
    plugin_duplicate["message"] = "This command_id was already executed."
    plugin_duplicate["error"] = {
        "code": "DUPLICATE_COMMAND",
        "message": "This command_id was already executed.",
        "details": None,
    }
    send_count = 0
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        nonlocal send_count
        send_count += 1
        if send_count == 1:
            return plugin_success
        raise AutoCADPluginHTTPError(409, plugin_duplicate)

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    first = client.post("/commands", json=command)
    retry = client.post("/commands", json=command)

    assert first.status_code == 200
    assert first.json()["data"]["created_count"] == 2
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "DUPLICATE_COMMAND"
    assert send_count == 2


def test_v04_limit_failure_never_checks_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    command["parameters"]["entities"] = []

    async def unexpected_health_check() -> bool:
        raise AssertionError("Invalid batches must not reach the plugin.")

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "is_connected",
        unexpected_health_check,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BATCH_LIMIT_EXCEEDED"


def test_v04_malformed_plugin_correlation_returns_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    plugin_result = raw_plugin_result(
        "execute-batch-success-v0.4.json"
    )
    plugin_result["data"]["entity_results"][1]["client_entity_id"] = "wrong"
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        return plugin_result

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 502
    body = response.json()
    assert body["schema_version"] == "0.4"
    assert body["error"]["code"] == "INVALID_PLUGIN_RESPONSE"


def test_v04_timeout_returns_structured_504(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        raise TimeoutError("The AutoCAD plugin timed out.")

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )

    response = client.post("/commands", json=command)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AUTOCAD_PLUGIN_TIMEOUT"


def test_v04_log_records_counts_without_geometry(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    command = load_fixture(REQUESTS / "execute-batch-v0.4.json")
    plugin_result = raw_plugin_result(
        "execute-batch-success-v0.4.json"
    )
    set_plugin_connection(monkeypatch, connected=True)

    async def fake_send_command(command: dict[str, Any]) -> dict[str, Any]:
        return plugin_result

    monkeypatch.setattr(
        api.autocad_plugin_client,
        "send_command",
        fake_send_command,
    )
    caplog.set_level(logging.INFO, logger=COMMAND_LOGGER_NAME)

    response = client.post("/commands", json=command)

    assert response.status_code == 200
    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == COMMAND_LOGGER_NAME
    ]
    completed = next(
        record
        for record in records
        if record["event"] == "command_completed"
    )
    assert completed["entity_count"] == 2
    assert completed["point_count"] == 5
    serialized = json.dumps(records)
    assert "parameters" not in serialized
    assert "vertices" not in serialized
    assert "client_entity_id" not in serialized
    assert "AI-BATCH" not in serialized
