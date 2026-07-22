from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from jsonschema import ValidationError, validate

from backend.src.mock_backend import (
    SCHEMA_PATH,
    load_json,
)

from backend.src.connection_manager import (
    autocad_connection_manager,
)

app = FastAPI(
    title="AutoCAD-AI Bridge",
    description="Local bridge for routing AutoCAD-AI commands.",
    version="0.1",
)

COMMAND_SCHEMA = load_json(SCHEMA_PATH)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Confirm that the local bridge is running."""
    return {
        "status": "ok",
        "service": "AutoCAD-AI bridge",
    }

@app.get("/applications")
def list_applications() -> dict[str, dict[str, bool]]:
    """Report whether AutoCAD is connected."""
    return {
        "autocad": {
            "connected": autocad_connection_manager.is_connected(),
        }
    }


@app.post("/commands")
async def submit_command(command: dict[str, Any]) -> dict[str, Any]:
    """Validate a command and wait for AutoCAD's result."""

    try:
        validate(
            instance=command,
            schema=COMMAND_SCHEMA,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid command: {error.message}",
        ) from error

    if not autocad_connection_manager.is_connected():
        raise HTTPException(
            status_code=503,
            detail="AutoCAD is not connected.",
        )

    try:
        return await autocad_connection_manager.send_command(command)
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@app.websocket("/ws/autocad")
async def autocad_websocket(websocket: WebSocket) -> None:
    """Maintain a WebSocket connection with the AutoCAD plugin."""

    await autocad_connection_manager.connect(websocket)

    try:
        while True:
            response = await websocket.receive_json()
            autocad_connection_manager.resolve_command(response)
    except WebSocketDisconnect:
        autocad_connection_manager.disconnect(websocket)
