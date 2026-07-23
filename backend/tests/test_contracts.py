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
