import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict

from backend.src.config import settings

BRIDGE_URL = settings.bridge_url
BRIDGE_TIMEOUT_SECONDS = settings.bridge_timeout_seconds
VALIDATED_BATCH_DIRECTORY = (
    settings.log_path.parent / "validated-batches"
)
VALIDATION_ID_PATTERN = re.compile(r"^validation-[0-9a-f]{64}$")

MCP_TRANSPORT_SECURITY = TransportSecuritySettings(
    allowed_hosts=[
        "127.0.0.1:*",
        "localhost:*",
        "host.docker.internal:*",
    ],
)

mcp = FastMCP(
    "AutoCAD-AI",
    instructions=(
        "Use these tools to inspect the local AutoCAD-AI bridge and send "
        "validated drawing commands to AutoCAD."
    ),
    host="127.0.0.1",
    port=8001,
    stateless_http=True,
    json_response=True,
    transport_security=MCP_TRANSPORT_SECURITY,
)


class BatchPoint(BaseModel):
    """One explicit world-space point in the command's declared units."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float = 0.0


class BatchLine(BaseModel):
    """One line candidate in an atomic batch."""

    model_config = ConfigDict(extra="forbid")

    client_entity_id: str
    entity_type: Literal["line"] = "line"
    layer: str
    create_layer_if_missing: bool = True
    start: BatchPoint
    end: BatchPoint


class BatchPolyline(BaseModel):
    """One lightweight polyline candidate in an atomic batch."""

    model_config = ConfigDict(extra="forbid")

    client_entity_id: str
    entity_type: Literal["polyline"] = "polyline"
    layer: str
    create_layer_if_missing: bool = True
    vertices: list[BatchPoint]
    closed: bool = False


BatchEntity = BatchLine | BatchPolyline


async def request_bridge(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send one request to the local AutoCAD-AI HTTP bridge."""

    try:
        async with httpx.AsyncClient(
            base_url=BRIDGE_URL,
            timeout=BRIDGE_TIMEOUT_SECONDS,
        ) as client:
            response = await client.request(
                method,
                path,
                json=payload,
            )
    except httpx.RequestError as error:
        return {
            "status": "error",
            "error": {
                "code": "BRIDGE_UNAVAILABLE",
                "message": f"Could not reach the AutoCAD-AI bridge: {error}",
            },
        }

    try:
        body = response.json()
    except ValueError:
        body = {
            "detail": response.text or "The bridge returned a non-JSON response."
        }

    if response.is_error:
        detail = body.get("detail", body) if isinstance(body, dict) else body
        structured_error = (
            detail.get("error")
            if isinstance(detail, dict) and isinstance(detail.get("error"), dict)
            else None
        )
        message = (
            structured_error.get("message", str(detail))
            if structured_error
            else (
                detail.get("message", str(detail))
                if isinstance(detail, dict)
                else str(detail)
            )
        )
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": {
                "code": (
                    structured_error.get("code", "BRIDGE_REQUEST_FAILED")
                    if structured_error
                    else "BRIDGE_REQUEST_FAILED"
                ),
                "message": message,
                "details": detail,
            },
        }

    if isinstance(body, dict):
        return body

    return {
        "status": "error",
        "error": {
            "code": "INVALID_BRIDGE_RESPONSE",
            "message": "The bridge response was not a JSON object.",
        },
    }


@mcp.tool()
async def get_bridge_health() -> dict[str, Any]:
    """Check whether the local AutoCAD-AI HTTP bridge is running."""

    return await request_bridge("GET", "/health")


@mcp.tool()
async def get_autocad_status() -> dict[str, Any]:
    """Check whether an AutoCAD application is connected to the bridge."""

    return await request_bridge("GET", "/applications")


def build_read_command(
    operation: str,
    parameters: dict[str, Any] | None = None,
    *,
    coordinate_system: str | None = None,
) -> dict[str, Any]:
    """Build one traceable schema-v0.3 read-only command."""

    command = {
        "schema_version": "0.3",
        "run_id": f"run-{uuid4()}",
        "import_id": None,
        "command_id": f"cmd-{uuid4()}",
        "submitted_at": datetime.now(UTC).isoformat(),
        "application": "autocad",
        "operation": operation,
        "parameters": parameters or {},
        "requires_approval": False,
    }
    if coordinate_system is not None:
        command["coordinate_system"] = coordinate_system
    return command


async def submit_read_command(
    operation: str,
    parameters: dict[str, Any] | None = None,
    *,
    coordinate_system: str | None = None,
) -> dict[str, Any]:
    """Submit one schema-v0.3 read-only command to the bridge."""

    return await request_bridge(
        "POST",
        "/commands",
        build_read_command(
            operation,
            parameters,
            coordinate_system=coordinate_system,
        ),
    )


def build_batch_command(
    *,
    import_id: str,
    expected_document_name: str,
    entities: list[BatchEntity],
    units: Literal[
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters",
    ],
    validate_only: bool,
    expected_document_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build one schema-v0.4 atomic batch command."""

    serialized_entities = [
        entity.model_dump()
        for entity in entities
    ]
    return {
        "schema_version": "0.4",
        "run_id": f"run-{uuid4()}",
        "import_id": import_id,
        "command_id": f"cmd-{uuid4()}",
        "submitted_at": datetime.now(UTC).isoformat(),
        "application": "autocad",
        "operation": "execute_batch",
        "parameters": {
            "validate_only": validate_only,
            "expected_document": {
                "name": expected_document_name,
                "fingerprint_guid": expected_document_fingerprint,
            },
            "entities": serialized_entities,
        },
        "units": units,
        "coordinate_system": "world",
        "requires_approval": False,
    }


async def submit_batch_command(
    *,
    import_id: str,
    expected_document_name: str,
    entities: list[BatchEntity],
    units: Literal[
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters",
    ],
    validate_only: bool,
    expected_document_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build and submit one schema-v0.4 batch."""

    return await request_bridge(
        "POST",
        "/commands",
        build_batch_command(
            import_id=import_id,
            expected_document_name=expected_document_name,
            expected_document_fingerprint=expected_document_fingerprint,
            entities=entities,
            units=units,
            validate_only=validate_only,
        ),
    )


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _validation_manifest(
    command: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    expected_document = copy.deepcopy(
        command["parameters"]["expected_document"]
    )
    actual_document = result.get("document")
    if (
        isinstance(actual_document, dict)
        and actual_document.get("fingerprint_guid")
    ):
        expected_document["fingerprint_guid"] = actual_document[
            "fingerprint_guid"
        ]

    return {
        "schema_version": "0.4",
        "import_id": command["import_id"],
        "application": "autocad",
        "operation": "execute_batch",
        "parameters": {
            "expected_document": expected_document,
            "entities": copy.deepcopy(command["parameters"]["entities"]),
        },
        "units": command["units"],
        "coordinate_system": "world",
        "requires_approval": False,
    }


def _validation_succeeded(
    command: dict[str, Any],
    result: dict[str, Any],
) -> bool:
    data = result.get("data")
    entity_count = len(command["parameters"]["entities"])
    return (
        result.get("status") == "success"
        and isinstance(data, dict)
        and data.get("validate_only") is True
        and data.get("validated_count") == entity_count
        and data.get("created_count") == 0
        and data.get("rolled_back") is False
    )


def _receipt_path(validation_id: str) -> Path:
    if not VALIDATION_ID_PATTERN.fullmatch(validation_id):
        raise ValueError("validation_id has an invalid format.")
    return VALIDATED_BATCH_DIRECTORY / f"{validation_id}.json"


def _write_receipt(receipt: dict[str, Any]) -> None:
    VALIDATED_BATCH_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = _receipt_path(receipt["validation_id"])
    temporary_path = path.with_suffix(f".tmp-{uuid4().hex}")
    temporary_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _save_validation_receipt(
    command: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    manifest = _validation_manifest(command, result)
    manifest_hash = hashlib.sha256(
        _canonical_json(manifest).encode("utf-8")
    ).hexdigest()
    validation_id = f"validation-{manifest_hash}"
    path = _receipt_path(validation_id)

    if path.exists():
        receipt = _load_validation_receipt(validation_id)
    else:
        receipt = {
            "validation_id": validation_id,
            "manifest_sha256": manifest_hash,
            "validated_at": datetime.now(UTC).isoformat(),
            "validation_command_id": command["command_id"],
            "validated_count": len(
                command["parameters"]["entities"]
            ),
            "manifest": manifest,
            "execution": {
                "run_id": f"run-{uuid4()}",
                "command_id": f"cmd-{uuid4()}",
                "submitted_at": datetime.now(UTC).isoformat(),
            },
            "execution_result": None,
        }
        _write_receipt(receipt)

    return {
        "validation_id": validation_id,
        "validated_count": receipt["validated_count"],
        "import_id": manifest["import_id"],
        "expected_document": manifest["parameters"][
            "expected_document"
        ],
        "units": manifest["units"],
        "execution_tool": "execute_validated_autocad_batch",
    }


def _load_validation_receipt(validation_id: str) -> dict[str, Any]:
    path = _receipt_path(validation_id)
    if not path.exists():
        raise FileNotFoundError(validation_id)

    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("The validation receipt could not be read.") from error

    manifest = receipt.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("The validation receipt has no manifest.")
    actual_hash = hashlib.sha256(
        _canonical_json(manifest).encode("utf-8")
    ).hexdigest()
    if (
        receipt.get("validation_id") != validation_id
        or receipt.get("manifest_sha256") != actual_hash
        or validation_id != f"validation-{actual_hash}"
    ):
        raise ValueError("The validation receipt failed its integrity check.")

    execution = receipt.get("execution")
    if not isinstance(execution, dict) or not all(
        execution.get(field)
        for field in ("run_id", "command_id", "submitted_at")
    ):
        raise ValueError("The validation receipt has no execution identity.")
    return receipt


def _execution_command(receipt: dict[str, Any]) -> dict[str, Any]:
    manifest = receipt["manifest"]
    execution = receipt["execution"]
    return {
        "schema_version": manifest["schema_version"],
        "run_id": execution["run_id"],
        "import_id": manifest["import_id"],
        "command_id": execution["command_id"],
        "submitted_at": execution["submitted_at"],
        "application": manifest["application"],
        "operation": manifest["operation"],
        "parameters": {
            "validate_only": False,
            "expected_document": copy.deepcopy(
                manifest["parameters"]["expected_document"]
            ),
            "entities": copy.deepcopy(
                manifest["parameters"]["entities"]
            ),
        },
        "units": manifest["units"],
        "coordinate_system": manifest["coordinate_system"],
        "requires_approval": manifest["requires_approval"],
    }


def _receipt_error(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
    }


@mcp.tool()
async def validate_autocad_batch(
    import_id: str,
    expected_document_name: str,
    entities: list[BatchEntity],
    units: Literal[
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters",
    ],
    expected_document_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Validate a line/polyline batch without creating or changing objects."""

    command = build_batch_command(
        import_id=import_id,
        expected_document_name=expected_document_name,
        expected_document_fingerprint=expected_document_fingerprint,
        entities=entities,
        units=units,
        validate_only=True,
    )
    result = await request_bridge("POST", "/commands", command)
    if _validation_succeeded(command, result):
        result = dict(result)
        result["validation_receipt"] = _save_validation_receipt(
            command,
            result,
        )
    return result


@mcp.tool()
async def execute_autocad_batch(
    import_id: str,
    expected_document_name: str,
    entities: list[BatchEntity],
    units: Literal[
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters",
    ],
    approved: bool,
    expected_document_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Execute an already reviewed batch atomically after explicit approval."""

    if not approved:
        return {
            "status": "error",
            "error": {
                "code": "APPROVAL_REQUIRED",
                "message": (
                    "Atomic batch execution requires explicit user approval. "
                    "Validate the batch first, present the result, and call "
                    "again only after the user approves."
                ),
            },
        }

    return await submit_batch_command(
        import_id=import_id,
        expected_document_name=expected_document_name,
        expected_document_fingerprint=expected_document_fingerprint,
        entities=entities,
        units=units,
        validate_only=False,
    )


@mcp.tool()
async def execute_validated_autocad_batch(
    validation_id: str,
    approved: bool,
) -> dict[str, Any]:
    """Execute the exact persisted manifest from a successful validation."""

    if not approved:
        return _receipt_error(
            "APPROVAL_REQUIRED",
            "Executing a validated batch requires approved: true.",
        )

    try:
        receipt = _load_validation_receipt(validation_id)
    except FileNotFoundError:
        return _receipt_error(
            "VALIDATION_RECEIPT_NOT_FOUND",
            f"Validation receipt '{validation_id}' was not found. "
            "Validate the complete batch again.",
        )
    except ValueError as error:
        return _receipt_error(
            "VALIDATION_RECEIPT_INVALID",
            str(error),
        )

    previous_result = receipt.get("execution_result")
    if (
        isinstance(previous_result, dict)
        and previous_result.get("status") == "success"
    ):
        replayed_result = copy.deepcopy(previous_result)
        replayed_result["validation_receipt"] = {
            "validation_id": validation_id,
            "replayed": True,
            "message": (
                "This validation receipt was already executed; the stored "
                "result was returned without sending another command."
            ),
        }
        return replayed_result

    result = await request_bridge(
        "POST",
        "/commands",
        _execution_command(receipt),
    )
    if result.get("status") == "success":
        receipt["execution_result"] = copy.deepcopy(result)
        receipt["executed_at"] = datetime.now(UTC).isoformat()
        _write_receipt(receipt)

    result = dict(result)
    result["validation_receipt"] = {
        "validation_id": validation_id,
        "replayed": False,
    }
    return result


@mcp.tool()
async def get_drawing_context() -> dict[str, Any]:
    """Read a compact summary of the active AutoCAD drawing."""

    return await submit_read_command("get_drawing_context")


@mcp.tool()
async def get_active_document() -> dict[str, Any]:
    """Read the identity and state of the active AutoCAD document."""

    return await submit_read_command("get_active_document")


@mcp.tool()
async def get_drawing_units() -> dict[str, Any]:
    """Read the insertion units configured in the active drawing."""

    return await submit_read_command("get_drawing_units")


@mcp.tool()
async def get_current_coordinate_system() -> dict[str, Any]:
    """Read the current AutoCAD UCS origin and axes in world coordinates."""

    return await submit_read_command("get_current_coordinate_system")


@mcp.tool()
async def get_drawing_extents() -> dict[str, Any]:
    """Read model-space geometric extents without changing the drawing."""

    return await submit_read_command("get_drawing_extents")


@mcp.tool()
async def list_layers(limit: int = 500) -> dict[str, Any]:
    """List layers in the active drawing, capped at 500 entries."""

    return await submit_read_command("list_layers", {"limit": limit})


@mcp.tool()
async def get_selected_entities(limit: int = 100) -> dict[str, Any]:
    """Read summaries for the entities currently selected in AutoCAD."""

    return await submit_read_command(
        "get_selected_entities",
        {"limit": limit},
    )


@mcp.tool()
async def get_entities_in_window(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    min_z: float = 0.0,
    max_z: float = 0.0,
    limit: int = 100,
) -> dict[str, Any]:
    """Read entities whose geometric extents intersect a world-space window."""

    return await submit_read_command(
        "get_entities_in_window",
        {
            "window_min": {"x": min_x, "y": min_y, "z": min_z},
            "window_max": {"x": max_x, "y": max_y, "z": max_z},
            "limit": limit,
        },
        coordinate_system="world",
    )


@mcp.tool()
async def get_entity_properties(object_id: str) -> dict[str, Any]:
    """Read properties for one AutoCAD entity identified by its handle."""

    return await submit_read_command(
        "get_entity_properties",
        {"object_id": object_id},
    )


@mcp.tool()
async def find_entities_by_import_id(
    import_id: str,
    limit: int = 100,
) -> dict[str, Any]:
    """Find entities carrying a specific AutoCAD-AI import identifier."""

    return await submit_read_command(
        "find_entities_by_import_id",
        {
            "target_import_id": import_id,
            "limit": limit,
        },
    )


@mcp.tool()
async def create_autocad_line(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    units: Literal[
        "inches",
        "feet",
        "millimeters",
        "centimeters",
        "meters",
    ],
    layer: str = "AI-WALL",
    start_z: float = 0.0,
    end_z: float = 0.0,
    create_layer_if_missing: bool = True,
    import_id: str | None = None,
) -> dict[str, Any]:
    """Create one line with explicit coordinates and optional import provenance."""

    run_id = f"run-{uuid4()}"
    command = {
        "schema_version": "0.2",
        "run_id": run_id,
        "import_id": import_id,
        "command_id": f"cmd-{uuid4()}",
        "submitted_at": datetime.now(UTC).isoformat(),
        "application": "autocad",
        "operation": "create_line",
        "parameters": {
            "start": {
                "x": start_x,
                "y": start_y,
                "z": start_z,
            },
            "end": {
                "x": end_x,
                "y": end_y,
                "z": end_z,
            },
            "layer": layer,
            "create_layer_if_missing": create_layer_if_missing,
        },
        "units": units,
        "coordinate_system": "world",
        "requires_approval": False,
    }

    return await request_bridge("POST", "/commands", command)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
