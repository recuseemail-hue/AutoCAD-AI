import json
from pathlib import Path

import pytest
from jsonschema import FormatChecker, validate

from backend.src.config import PROJECT_ROOT
from backend.src.contracts import (
    ContractValidationError,
    bridge_error_payload,
    load_schema,
    validate_command,
    validate_result,
)


def load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_v01_command_remains_supported() -> None:
    command = load_fixture(
        PROJECT_ROOT / "examples" / "requests" / "create-line.json"
    )

    assert validate_command(command) == "0.1"


def test_v02_command_and_result_fixtures_validate() -> None:
    command = load_fixture(
        PROJECT_ROOT
        / "examples"
        / "requests"
        / "create-line-v0.2.json"
    )
    result = load_fixture(
        PROJECT_ROOT
        / "examples"
        / "responses"
        / "create-line-success-v0.2.json"
    )

    assert validate_command(command) == "0.2"
    validate_result(result)


def test_v03_read_command_and_result_fixtures_validate() -> None:
    command = load_fixture(
        PROJECT_ROOT
        / "examples"
        / "requests"
        / "get-drawing-context-v0.3.json"
    )
    result = load_fixture(
        PROJECT_ROOT
        / "examples"
        / "responses"
        / "get-drawing-context-success-v0.3.json"
    )

    assert validate_command(command) == "0.3"
    validate_result(result)


@pytest.mark.parametrize(
    ("operation", "parameters", "extra"),
    [
        ("get_drawing_context", {}, {}),
        ("get_active_document", {}, {}),
        ("get_drawing_units", {}, {}),
        ("get_current_coordinate_system", {}, {}),
        ("get_drawing_extents", {}, {}),
        ("list_layers", {"limit": 50}, {}),
        ("get_selected_entities", {"limit": 50}, {}),
        (
            "get_entities_in_window",
            {
                "window_min": {"x": 0, "y": 0, "z": 0},
                "window_max": {"x": 100, "y": 100, "z": 0},
                "limit": 50,
            },
            {"coordinate_system": "world"},
        ),
        ("get_entity_properties", {"object_id": "2AF"}, {}),
        (
            "find_entities_by_import_id",
            {"target_import_id": "import-001", "limit": 50},
            {},
        ),
    ],
)
def test_all_v03_read_operations_validate(
    operation: str,
    parameters: dict,
    extra: dict,
) -> None:
    command = {
        "schema_version": "0.3",
        "run_id": "run-read-001",
        "import_id": None,
        "command_id": "cmd-read-001",
        "submitted_at": "2026-07-23T12:00:00Z",
        "application": "autocad",
        "operation": operation,
        "parameters": parameters,
        "requires_approval": False,
        **extra,
    }

    assert validate_command(command) == "0.3"


def test_v03_rejects_mutations_and_wrong_read_parameters() -> None:
    command = {
        "schema_version": "0.3",
        "run_id": "run-read-001",
        "import_id": None,
        "command_id": "cmd-read-001",
        "submitted_at": "2026-07-23T12:00:00Z",
        "application": "autocad",
        "operation": "create_line",
        "parameters": {},
        "requires_approval": False,
    }
    with pytest.raises(ContractValidationError):
        validate_command(command)

    command["operation"] = "get_entity_properties"
    with pytest.raises(ContractValidationError):
        validate_command(command)


def test_unsupported_command_schema_is_rejected() -> None:
    with pytest.raises(
        ContractValidationError,
        match="Unsupported schema_version",
    ) as error:
        validate_command({"schema_version": "9.9"})

    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_bridge_error_payload_matches_v02_schema() -> None:
    payload = bridge_error_payload(
        "AUTOCAD_DISCONNECTED",
        "AutoCAD is not connected.",
        command={
            "run_id": "run-test-001",
            "command_id": "cmd-test-001",
        },
    )

    validate(
        instance=payload,
        schema=load_schema("0.2", "error"),
        format_checker=FormatChecker(),
    )


def test_bridge_error_payload_matches_v03_schema() -> None:
    payload = bridge_error_payload(
        "AUTOCAD_DISCONNECTED",
        "AutoCAD is not connected.",
        command={
            "schema_version": "0.3",
            "run_id": "run-read-001",
            "command_id": "cmd-read-001",
        },
    )

    validate(
        instance=payload,
        schema=load_schema("0.3", "error"),
        format_checker=FormatChecker(),
    )
