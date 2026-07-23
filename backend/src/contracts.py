import json
import math
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
TRACEABLE_SCHEMA_VERSIONS = ("0.2", "0.3", "0.4")
BATCH_SCHEMA_VERSION = "0.4"
BATCH_MAX_ENTITIES = 500
BATCH_MAX_POINTS = 50_000


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

    if version == BATCH_SCHEMA_VERSION:
        _validate_v04_batch_limits(command)

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

    if version == BATCH_SCHEMA_VERSION:
        _validate_v04_batch_geometry(command)

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


def validate_plugin_result(result: dict[str, Any]) -> None:
    """Validate a raw plugin response when a formal plugin schema exists."""

    if result.get("schema_version") != BATCH_SCHEMA_VERSION:
        return

    try:
        validate(
            instance=result,
            schema=load_schema(BATCH_SCHEMA_VERSION, "plugin-result"),
            format_checker=FORMAT_CHECKER,
        )
    except ValidationError as error:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            f"Invalid plugin result: {error.message}",
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

    _validate_plugin_correlation(command, plugin_result)
    if schema_version == BATCH_SCHEMA_VERSION:
        validate_plugin_result(plugin_result)

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
    if schema_version == BATCH_SCHEMA_VERSION:
        _validate_v04_result_semantics(command, normalized)
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

    payload = {
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
    if schema_version == BATCH_SCHEMA_VERSION:
        payload["import_id"] = command.get("import_id")
    return payload


def get_batch_counts(command: dict[str, Any]) -> tuple[int, int]:
    """Return safe entity and point counts without exposing batch geometry."""

    parameters = command.get("parameters")
    if not isinstance(parameters, dict):
        return (0, 0)

    entities = parameters.get("entities")
    if not isinstance(entities, list):
        return (0, 0)

    point_count = 0
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        if entity.get("entity_type") == "line":
            point_count += 2
        elif entity.get("entity_type") == "polyline":
            vertices = entity.get("vertices")
            if isinstance(vertices, list):
                point_count += len(vertices)

    return (len(entities), point_count)


def _validate_v04_batch_limits(command: dict[str, Any]) -> None:
    entity_count, point_count = get_batch_counts(command)
    parameters = command.get("parameters")
    entities = (
        parameters.get("entities")
        if isinstance(parameters, dict)
        else None
    )
    if not isinstance(entities, list):
        return

    if entity_count < 1 or entity_count > BATCH_MAX_ENTITIES:
        raise ContractValidationError(
            "BATCH_LIMIT_EXCEEDED",
            "Atomic batches must contain between "
            f"1 and {BATCH_MAX_ENTITIES} entities; received {entity_count}.",
        )

    if point_count > BATCH_MAX_POINTS:
        raise ContractValidationError(
            "BATCH_LIMIT_EXCEEDED",
            "Atomic batches may contain at most "
            f"{BATCH_MAX_POINTS} total points; received {point_count}.",
        )


def _validate_v04_batch_geometry(command: dict[str, Any]) -> None:
    entities = command["parameters"]["entities"]
    seen_ids: set[str] = set()

    for entity in entities:
        client_entity_id = entity["client_entity_id"]
        if client_entity_id in seen_ids:
            raise ContractValidationError(
                "INVALID_BATCH_GEOMETRY",
                f"Duplicate client_entity_id '{client_entity_id}'.",
            )
        seen_ids.add(client_entity_id)

        if entity["entity_type"] == "line":
            points = [entity["start"], entity["end"]]
            _validate_finite_points(client_entity_id, points)
            if _point_key(points[0]) == _point_key(points[1]):
                raise ContractValidationError(
                    "INVALID_BATCH_GEOMETRY",
                    f"Line '{client_entity_id}' has zero length.",
                )
            continue

        vertices = entity["vertices"]
        _validate_finite_points(client_entity_id, vertices)
        vertex_keys = [_point_key(point) for point in vertices]
        for index in range(1, len(vertex_keys)):
            if vertex_keys[index] == vertex_keys[index - 1]:
                raise ContractValidationError(
                    "INVALID_BATCH_GEOMETRY",
                    "Polyline "
                    f"'{client_entity_id}' has duplicate consecutive vertices "
                    f"at indexes {index - 1} and {index}.",
                )

        if entity["closed"]:
            if vertex_keys[0] == vertex_keys[-1]:
                raise ContractValidationError(
                    "INVALID_BATCH_GEOMETRY",
                    "Closed polyline "
                    f"'{client_entity_id}' must use closed: true without "
                    "repeating its first vertex at the end.",
                )
            if len(set(vertex_keys)) < 3:
                raise ContractValidationError(
                    "INVALID_BATCH_GEOMETRY",
                    f"Closed polyline '{client_entity_id}' needs at least "
                    "three distinct vertices.",
                )


def _validate_finite_points(
    client_entity_id: str,
    points: list[dict[str, Any]],
) -> None:
    for index, point in enumerate(points):
        for coordinate in ("x", "y", "z"):
            if not math.isfinite(point[coordinate]):
                raise ContractValidationError(
                    "INVALID_BATCH_GEOMETRY",
                    f"Entity '{client_entity_id}' point {index} has a "
                    f"non-finite {coordinate} coordinate.",
                )


def _point_key(point: dict[str, Any]) -> tuple[float, float, float]:
    return (point["x"], point["y"], point["z"])


def _validate_plugin_correlation(
    command: dict[str, Any],
    plugin_result: dict[str, Any],
) -> None:
    for field in (
        "schema_version",
        "run_id",
        "import_id",
        "command_id",
        "application",
        "operation",
    ):
        if plugin_result.get(field) != command.get(field):
            raise ContractValidationError(
                "INVALID_PLUGIN_RESPONSE",
                f"Plugin result {field} did not match the command.",
            )


def _validate_v04_result_semantics(
    command: dict[str, Any],
    result: dict[str, Any],
) -> None:
    expected_entities = command["parameters"]["entities"]
    expected_ids = [
        entity["client_entity_id"]
        for entity in expected_entities
    ]
    expected_id_set = set(expected_ids)
    expected_by_id = {
        entity["client_entity_id"]: entity
        for entity in expected_entities
    }
    validate_only = command["parameters"]["validate_only"]
    data = result.get("data")

    if result["status"] == "error":
        if result["affected_objects"] or result["undo_token"] is not None:
            raise ContractValidationError(
                "INVALID_PLUGIN_RESPONSE",
                "An atomic batch error cannot report created objects or an "
                "undo token.",
            )
        error_code = result["error"]["code"]
        if (
            error_code in {
                "BATCH_EXECUTION_FAILED",
                "BATCH_ROLLED_BACK",
            }
            and (
                not isinstance(data, dict)
                or not data["rolled_back"]
            )
        ):
            raise ContractValidationError(
                "INVALID_PLUGIN_RESPONSE",
                f"{error_code} must report rolled_back true.",
            )
        if isinstance(data, dict):
            if data["validate_only"] != validate_only:
                raise ContractValidationError(
                    "INVALID_PLUGIN_RESPONSE",
                    "Plugin result validate_only did not match the command.",
                )
            if data["created_count"] != 0:
                raise ContractValidationError(
                    "INVALID_PLUGIN_RESPONSE",
                    "An atomic batch error must report created_count 0.",
                )
        return

    if not isinstance(data, dict):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "A successful atomic batch result requires data.",
        )
    if data["validate_only"] != validate_only:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Plugin result validate_only did not match the command.",
        )
    if data["validated_count"] != len(expected_entities):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Plugin result validated_count did not match the batch.",
        )
    if data["rolled_back"]:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "A successful atomic batch cannot report rolled_back true.",
        )

    entity_results = data["entity_results"]
    result_ids = [
        entity_result["client_entity_id"]
        for entity_result in entity_results
    ]
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != expected_id_set:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Plugin entity results did not correlate one-to-one with the batch.",
        )
    if any(
        entity_result["entity_type"]
        != expected_by_id[entity_result["client_entity_id"]]["entity_type"]
        or entity_result["layer"].casefold()
        != expected_by_id[entity_result["client_entity_id"]]["layer"].casefold()
        for entity_result in entity_results
    ):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Plugin entity result type or layer did not match the command.",
        )

    expected_document = command["parameters"]["expected_document"]
    actual_document = result.get("document")
    if not isinstance(actual_document, dict):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "A successful atomic batch requires active-document identity.",
        )
    if actual_document.get("name").casefold() != expected_document["name"].casefold():
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Successful batch result document name did not match the command.",
        )
    expected_fingerprint = expected_document.get("fingerprint_guid")
    if (
        expected_fingerprint is not None
        and actual_document.get("fingerprint_guid", "").casefold()
        != expected_fingerprint.casefold()
    ):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Successful batch result document fingerprint did not match the "
            "command.",
        )

    if validate_only:
        if (
            data["created_count"] != 0
            or result["affected_objects"]
            or result["undo_token"] is not None
        ):
            raise ContractValidationError(
                "INVALID_PLUGIN_RESPONSE",
                "Validate-only results cannot report created objects or an "
                "undo token.",
            )
        if any(
            entity_result["status"] != "validated"
            or entity_result["object_id"] is not None
            for entity_result in entity_results
        ):
            raise ContractValidationError(
                "INVALID_PLUGIN_RESPONSE",
                "Validate-only entity results must be validated without "
                "object handles.",
            )
        return

    if data["created_count"] != len(expected_entities):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Plugin result created_count did not match the batch.",
        )
    if not isinstance(result["undo_token"], str) or not result["undo_token"]:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "A successful execution requires one batch undo token.",
        )
    if any(
        entity_result["status"] != "created"
        or not entity_result["object_id"]
        for entity_result in entity_results
    ):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Executed entity results must be created with object handles.",
        )

    affected_objects = result["affected_objects"]
    affected_ids = {
        affected["client_entity_id"]
        for affected in affected_objects
    }
    if len(affected_objects) != len(expected_entities) or affected_ids != expected_id_set:
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Affected objects did not correlate one-to-one with the batch.",
        )
    expected_object_types = {
        "line": "LINE",
        "polyline": "LWPOLYLINE",
    }
    if any(
        affected["object_type"]
        != expected_object_types[
            expected_by_id[affected["client_entity_id"]]["entity_type"]
        ]
        for affected in affected_objects
    ):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Affected-object type did not match the requested entity type.",
        )
    handles_by_id = {
        entity_result["client_entity_id"]: entity_result["object_id"]
        for entity_result in entity_results
    }
    if any(
        handles_by_id[affected["client_entity_id"]] != affected["object_id"]
        for affected in affected_objects
    ):
        raise ContractValidationError(
            "INVALID_PLUGIN_RESPONSE",
            "Affected-object handles did not match entity-result handles.",
        )
