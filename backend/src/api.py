from typing import Any

from fastapi import FastAPI, HTTPException
from jsonschema import ValidationError, validate

from backend.src.mock_backend import (
    SCHEMA_PATH,
    load_json,
    process_command,
)


app = FastAPI(
    title="AutoCAD-AI Mock Bridge",
    description="Temporary local bridge for testing AutoCAD-AI commands.",
    version="0.1",
)

COMMAND_SCHEMA = load_json(SCHEMA_PATH)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Confirm that the local bridge is running."""
    return {
        "status": "ok",
        "service": "AutoCAD-AI mock bridge",
    }


@app.post("/commands")
def submit_command(command: dict[str, Any]) -> dict[str, Any]:
    """Validate and process one AutoCAD-AI command."""

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

    try:
        return process_command(command)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error