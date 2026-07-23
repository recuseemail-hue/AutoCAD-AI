import os
from typing import Any, Literal
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


BRIDGE_URL = os.getenv(
    "AUTOCAD_AI_BRIDGE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

BRIDGE_TIMEOUT_SECONDS = 40.0

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
        message = (
            detail.get("message", str(detail))
            if isinstance(detail, dict)
            else str(detail)
        )
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": {
                "code": "BRIDGE_REQUEST_FAILED",
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
) -> dict[str, Any]:
    """Create one line in AutoCAD using explicit coordinates and units."""

    command = {
        "schema_version": "0.1",
        "command_id": f"odysseus-{uuid4()}",
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
