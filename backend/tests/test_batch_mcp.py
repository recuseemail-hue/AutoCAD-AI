import json
from typing import Any

import pytest

from backend.src import odysseus_mcp
from backend.src.contracts import validate_command


def sample_entities() -> list[odysseus_mcp.BatchEntity]:
    return [
        odysseus_mcp.BatchLine(
            client_entity_id="line-001",
            layer="AI-BATCH",
            start=odysseus_mcp.BatchPoint(x=0, y=0),
            end=odysseus_mcp.BatchPoint(x=120, y=0),
        ),
        odysseus_mcp.BatchPolyline(
            client_entity_id="polyline-001",
            layer="AI-BATCH",
            vertices=[
                odysseus_mcp.BatchPoint(x=0, y=24),
                odysseus_mcp.BatchPoint(x=60, y=24),
                odysseus_mcp.BatchPoint(x=60, y=60),
            ],
        ),
    ]


def validation_success(entity_count: int = 2) -> dict[str, Any]:
    return {
        "status": "success",
        "message": "Atomic batch validated successfully.",
        "data": {
            "validate_only": True,
            "validated_count": entity_count,
            "created_count": 0,
            "rolled_back": False,
        },
        "document": {
            "name": "Drawing1.dwg",
            "fingerprint_guid": (
                "11111111-1111-1111-1111-111111111111"
            ),
        },
    }


def test_batch_builder_emits_schema_valid_v04_command() -> None:
    command = odysseus_mcp.build_batch_command(
        import_id="import-test-001",
        expected_document_name="Drawing1.dwg",
        expected_document_fingerprint=(
            "11111111-1111-1111-1111-111111111111"
        ),
        entities=sample_entities(),
        units="inches",
        validate_only=True,
    )

    assert validate_command(command) == "0.4"
    assert command["run_id"].startswith("run-")
    assert command["command_id"].startswith("cmd-")
    assert command["import_id"] == "import-test-001"
    assert command["parameters"]["validate_only"] is True
    assert command["parameters"]["entities"][0] == {
        "client_entity_id": "line-001",
        "entity_type": "line",
        "layer": "AI-BATCH",
        "create_layer_if_missing": True,
        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
        "end": {"x": 120.0, "y": 0.0, "z": 0.0},
    }
    assert command["parameters"]["entities"][1]["closed"] is False


@pytest.mark.anyio
async def test_validate_batch_tool_submits_validate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/commands"
        assert payload is not None
        captured.update(payload)
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.validate_autocad_batch(
        import_id="import-test-001",
        expected_document_name="Drawing1.dwg",
        entities=sample_entities(),
        units="inches",
    )

    assert result["status"] == "success"
    assert captured["schema_version"] == "0.4"
    assert captured["operation"] == "execute_batch"
    assert captured["parameters"]["validate_only"] is True
    assert captured["requires_approval"] is False


@pytest.mark.anyio
async def test_execute_batch_requires_explicit_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_request(*args: object, **kwargs: object) -> dict:
        raise AssertionError("Unapproved batches must not reach the bridge.")

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        unexpected_request,
    )

    result = await odysseus_mcp.execute_autocad_batch(
        import_id="import-test-001",
        expected_document_name="Drawing1.dwg",
        entities=sample_entities(),
        units="inches",
        approved=False,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "APPROVAL_REQUIRED"


@pytest.mark.anyio
async def test_approved_execute_batch_submits_write_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        captured.update(payload)
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.execute_autocad_batch(
        import_id="import-test-001",
        expected_document_name="Drawing1.dwg",
        expected_document_fingerprint=(
            "11111111-1111-1111-1111-111111111111"
        ),
        entities=sample_entities(),
        units="inches",
        approved=True,
    )

    assert result["status"] == "success"
    assert captured["parameters"]["validate_only"] is False
    assert captured["parameters"]["expected_document"] == {
        "name": "Drawing1.dwg",
        "fingerprint_guid": "11111111-1111-1111-1111-111111111111",
    }


@pytest.mark.anyio
async def test_mcp_advertises_both_batch_tools() -> None:
    tools = await odysseus_mcp.mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert len(tools) == 16
    assert "validate_autocad_batch" in tool_names
    assert "execute_autocad_batch" in tool_names
    assert "execute_validated_autocad_batch" in tool_names


@pytest.mark.anyio
async def test_batch_tool_schema_does_not_require_union_tag_extraction() -> None:
    tools = await odysseus_mcp.mcp.list_tools()
    validate_tool = next(
        tool
        for tool in tools
        if tool.name == "validate_autocad_batch"
    )
    entity_schema = validate_tool.inputSchema["properties"]["entities"]["items"]

    assert "discriminator" not in entity_schema


@pytest.mark.anyio
async def test_mcp_infers_entity_types_when_odysseus_omits_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        captured.update(payload)
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )
    tool = odysseus_mcp.mcp._tool_manager.get_tool(
        "validate_autocad_batch"
    )
    assert tool is not None

    result = await tool.run(
        {
            "import_id": "import-odysseus-001",
            "expected_document_name": "Drawing1.dwg",
            "units": "inches",
            "entities": [
                {
                    "client_entity_id": "line-001",
                    "layer": "AI-BATCH",
                    "start": {"x": 0, "y": 0},
                    "end": {"x": 120, "y": 0},
                },
                {
                    "client_entity_id": "polyline-001",
                    "layer": "AI-BATCH",
                    "vertices": [
                        {"x": 0, "y": 24},
                        {"x": 60, "y": 24},
                        {"x": 60, "y": 60},
                    ],
                },
            ],
        }
    )

    assert result["status"] == "success"
    serialized = captured["parameters"]["entities"]
    assert serialized[0]["entity_type"] == "line"
    assert serialized[1]["entity_type"] == "polyline"


@pytest.mark.anyio
async def test_validation_receipt_executes_exact_persisted_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(
        odysseus_mcp,
        "VALIDATED_BATCH_DIRECTORY",
        tmp_path,
    )
    submitted: list[dict[str, Any]] = []

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        submitted.append(payload)
        if payload["parameters"]["validate_only"]:
            return validation_success()
        return {
            "status": "success",
            "command_id": payload["command_id"],
            "import_id": payload["import_id"],
            "data": {
                "validate_only": False,
                "validated_count": 2,
                "created_count": 2,
                "rolled_back": False,
            },
        }

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    validation = await odysseus_mcp.validate_autocad_batch(
        import_id="import-receipt-001",
        expected_document_name="Drawing1.dwg",
        entities=sample_entities(),
        units="inches",
    )
    validation_id = validation["validation_receipt"]["validation_id"]
    execution = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id=validation_id,
        approved=True,
    )

    assert execution["status"] == "success"
    assert len(submitted) == 2
    validated_entities = submitted[0]["parameters"]["entities"]
    executed_entities = submitted[1]["parameters"]["entities"]
    assert executed_entities == validated_entities
    assert submitted[1]["parameters"]["validate_only"] is False
    assert submitted[1]["parameters"]["expected_document"][
        "fingerprint_guid"
    ] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.anyio
async def test_validated_execution_requires_approval_without_bridge_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_request(*args: object, **kwargs: object) -> dict:
        raise AssertionError("Unapproved receipts must not reach the bridge.")

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        unexpected_request,
    )

    result = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id="validation-" + ("0" * 64),
        approved=False,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "APPROVAL_REQUIRED"


@pytest.mark.anyio
async def test_missing_and_tampered_validation_receipts_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(
        odysseus_mcp,
        "VALIDATED_BATCH_DIRECTORY",
        tmp_path,
    )
    missing_id = "validation-" + ("0" * 64)
    missing = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id=missing_id,
        approved=True,
    )
    assert missing["error"]["code"] == "VALIDATION_RECEIPT_NOT_FOUND"

    command = odysseus_mcp.build_batch_command(
        import_id="import-receipt-002",
        expected_document_name="Drawing1.dwg",
        entities=sample_entities(),
        units="inches",
        validate_only=True,
    )
    summary = odysseus_mcp._save_validation_receipt(
        command,
        validation_success(),
    )
    path = tmp_path / f"{summary['validation_id']}.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["manifest"]["units"] = "meters"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    tampered = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id=summary["validation_id"],
        approved=True,
    )
    assert tampered["error"]["code"] == "VALIDATION_RECEIPT_INVALID"


@pytest.mark.anyio
async def test_successful_receipt_replay_does_not_resubmit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(
        odysseus_mcp,
        "VALIDATED_BATCH_DIRECTORY",
        tmp_path,
    )
    command = odysseus_mcp.build_batch_command(
        import_id="import-receipt-003",
        expected_document_name="Drawing1.dwg",
        entities=sample_entities(),
        units="inches",
        validate_only=True,
    )
    summary = odysseus_mcp._save_validation_receipt(
        command,
        validation_success(),
    )
    calls = 0

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert payload is not None
        return {
            "status": "success",
            "command_id": payload["command_id"],
            "data": {"created_count": 2},
        }

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )
    first = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id=summary["validation_id"],
        approved=True,
    )
    second = await odysseus_mcp.execute_validated_autocad_batch(
        validation_id=summary["validation_id"],
        approved=True,
    )

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["validation_receipt"]["replayed"] is True
    assert calls == 1
