from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from backend.src.config import settings

BRIDGE_URL = settings.bridge_url
BRIDGE_TIMEOUT_SECONDS = settings.bridge_timeout_seconds

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
