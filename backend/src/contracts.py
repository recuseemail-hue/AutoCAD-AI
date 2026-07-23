import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker, ValidationError, validate

from backend.src.config import (
    BRIDGE_VERSION,
    PROJECT_ROOT,
    SUPPORTED_SCHEMA_VERSIONS,
)


SCHEMA_ROOT = PROJECT_ROOT / "schemas"
FORMAT_CHECKER = FormatChecker()
TRACEABLE_SCHEMA_VERSIONS = ("0.2", "0.3")


class ContractValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def load_schema(version: str, schema_name: str) -> dict[str, Any]:
    path = SCHEMA_ROOT / f"v{version}" / f"{schema_name}.schema.json"
    if not path.exists():
        raise ContractValidationError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"Unsupported schema_version '{version}'.",
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_command(command: dict[str, Any]) -> str:
    version = command.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ContractValidationError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"Unsupported schema_version '{version}'.",
        )

    try:
        validate(
            instance=command,
            schema=load_schema(version, "command"),
            format_checker=FORMAT_CHECKER,
        )
    except ValidationError as error:
        raise ContractValidationError(
            "INVALID_COMMAND",
            f"Invalid command: {error.message}",
        ) from error

    return version


def validate_result(result: dict[str, Any]) -> None:
    version = result.get("schema_version")
    if version not in TRACEABLE_SCHEMA_VERSIONS:
        return

    try:
        validate(
            instance=result,
            schema=load_schema(version, "result"),
            format_checker=FORMAT_CHECKER,
        )
    except ValidationError as error:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            f"Invalid normalized plugin result: {error.message}",
        ) from error


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_traceable_result(
    command: dict[str, Any],
    plugin_result: dict[str, Any],
    bridge_received_at: str,
) -> dict[str, Any]:
    schema_version = command["schema_version"]
    if schema_version not in TRACEABLE_SCHEMA_VERSIONS:
        raise ContractValidationError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"Cannot normalize schema_version '{schema_version}'.",
        )

    status = plugin_result.get("status", "error")
    error = plugin_result.get("error")
    if status == "error" and not isinstance(error, dict):
        error = {
            "code": "AUTOCAD_PLUGIN_ERROR",
            "message": plugin_result.get(
                "message",
                "The AutoCAD plugin reported an error.",
            ),
            "details": None,
        }
    elif status == "success":
        error = None

    document = plugin_result.get("document")
    if not isinstance(document, dict) or not document.get("name"):
        document = None

    normalized = {
        "schema_version": schema_version,
        "run_id": command["run_id"],
        "import_id": command["import_id"],
        "command_id": command["command_id"],
        "application": command["application"],
        "operation": command["operation"],
        "status": status,
        "message": plugin_result.get(
            "message",
            "The AutoCAD plugin returned no message.",
        ),
        "error": error,
        "affected_objects": plugin_result.get("affected_objects", []),
        "data": plugin_result.get("data"),
        "undo_token": plugin_result.get("undo_token"),
        "warnings": plugin_result.get("warnings", []),
        "document": document,
        "versions": {
            "bridge": BRIDGE_VERSION,
            "plugin": plugin_result.get("plugin_version", "unknown"),
        },
        "timestamps": {
            "submitted_at": command["submitted_at"],
            "bridge_received_at": bridge_received_at,
            "completed_at": plugin_result.get("completed_at", utc_now()),
        },
    }
    validate_result(normalized)
    return normalized


def bridge_error_payload(
    code: str,
    message: str,
    *,
    command: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command = command or {}
    schema_version = command.get("schema_version")
    if schema_version not in TRACEABLE_SCHEMA_VERSIONS:
        schema_version = "0.2"

    return {
        "schema_version": schema_version,
        "status": "error",
        "run_id": command.get("run_id"),
        "command_id": command.get("command_id"),
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "bridge_version": BRIDGE_VERSION,
        "timestamp": utc_now(),
    }
