from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
)
from jsonschema import ValidationError, validate

from backend.src.mock_backend import (
    SCHEMA_PATH,
    load_json,
)

from backend.src.connection_manager import (
    AutoCADPluginHTTPError,
    autocad_plugin_client,
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
async def list_applications() -> dict[str, dict[str, bool]]:
    """Report whether AutoCAD is connected."""
    return {
        "autocad": {
            "connected": await autocad_plugin_client.is_connected(),
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

    if not await autocad_plugin_client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="AutoCAD is not connected.",
        )

    try:
        return await autocad_plugin_client.send_command(command)
    except AutoCADPluginHTTPError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.body,
        ) from error
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
            status_code=502,
            detail=str(error),
        ) from error
