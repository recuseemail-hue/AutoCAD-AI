from time import perf_counter
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.src.config import (
    BRIDGE_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)
from backend.src.connection_manager import (
    AutoCADPluginHTTPError,
    autocad_plugin_client,
)
from backend.src.contracts import (
    ContractValidationError,
    TRACEABLE_SCHEMA_VERSIONS,
    bridge_error_payload,
    normalize_traceable_result,
    utc_now,
    validate_command,
)
from backend.src.observability import log_command_event


app = FastAPI(
    title="AutoCAD-AI Bridge",
    description="Local bridge for routing AutoCAD-AI commands.",
    version=BRIDGE_VERSION,
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    command: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    command = command or {}
    if command.get("schema_version") == "0.1":
        detail: Any = details if details is not None else message
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
        )

    return JSONResponse(
        status_code=status_code,
        content=bridge_error_payload(
            code,
            message,
            command=command,
            details=details,
        ),
    )


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Confirm that the local bridge is running and report contract support."""

    return {
        "status": "ok",
        "service": "AutoCAD-AI bridge",
        "version": BRIDGE_VERSION,
        "supported_schema_versions": list(SUPPORTED_SCHEMA_VERSIONS),
    }


@app.get("/applications")
async def list_applications() -> dict[str, dict[str, Any]]:
    """Report whether AutoCAD is connected and identify the loaded plugin."""

    plugin_health = await autocad_plugin_client.get_health()
    return {
        "autocad": {
            "connected": plugin_health is not None,
            "plugin_version": (
                plugin_health.get("plugin_version")
                if plugin_health is not None
                else None
            ),
            "supported_schema_versions": (
                plugin_health.get("supported_schema_versions", [])
                if plugin_health is not None
                else []
            ),
        }
    }


@app.post("/commands", response_model=None)
async def submit_command(
    command: dict[str, Any],
) -> dict[str, Any] | JSONResponse:
    """Validate, trace, forward, normalize, and return one AutoCAD command."""

    bridge_received_at = utc_now()
    started_at = perf_counter()

    try:
        schema_version = validate_command(command)
    except ContractValidationError as error:
        log_command_event(
            "command_rejected",
            command=command,
            status="error",
            error_code=error.code,
        )
        return error_response(
            422,
            error.code,
            str(error),
            command=command,
        )

    log_command_event(
        "command_accepted",
        command=command,
        status="accepted",
    )

    if not await autocad_plugin_client.is_connected():
        duration_ms = (perf_counter() - started_at) * 1000
        log_command_event(
            "command_failed",
            command=command,
            status="error",
            error_code="AUTOCAD_DISCONNECTED",
            duration_ms=duration_ms,
        )
        return error_response(
            503,
            "AUTOCAD_DISCONNECTED",
            "AutoCAD is not connected.",
            command=command,
        )

    try:
        plugin_result = await autocad_plugin_client.send_command(command)
        result = (
            normalize_traceable_result(
                command,
                plugin_result,
                bridge_received_at,
            )
            if schema_version in TRACEABLE_SCHEMA_VERSIONS
            else plugin_result
        )
    except AutoCADPluginHTTPError as error:
        duration_ms = (perf_counter() - started_at) * 1000
        if schema_version in TRACEABLE_SCHEMA_VERSIONS:
            try:
                result = normalize_traceable_result(
                    command,
                    error.body,
                    bridge_received_at,
                )
            except ContractValidationError as validation_error:
                log_command_event(
                    "command_failed",
                    command=command,
                    status="error",
                    error_code=validation_error.code,
                    duration_ms=duration_ms,
                )
                return error_response(
                    502,
                    validation_error.code,
                    str(validation_error),
                    command=command,
                )

            error_code = (
                result["error"]["code"]
                if isinstance(result.get("error"), dict)
                else "AUTOCAD_PLUGIN_ERROR"
            )
            log_command_event(
                "command_failed",
                command=command,
                status="error",
                error_code=error_code,
                duration_ms=duration_ms,
            )
            return JSONResponse(
                status_code=error.status_code,
                content=result,
            )

        log_command_event(
            "command_failed",
            command=command,
            status="error",
            error_code="AUTOCAD_PLUGIN_ERROR",
            duration_ms=duration_ms,
        )
        return error_response(
            error.status_code,
            "AUTOCAD_PLUGIN_ERROR",
            str(error),
            command=command,
            details=error.body,
        )
    except RuntimeError as error:
        duration_ms = (perf_counter() - started_at) * 1000
        log_command_event(
            "command_failed",
            command=command,
            status="error",
            error_code="AUTOCAD_PLUGIN_UNAVAILABLE",
            duration_ms=duration_ms,
        )
        return error_response(
            503,
            "AUTOCAD_PLUGIN_UNAVAILABLE",
            str(error),
            command=command,
        )
    except TimeoutError as error:
        duration_ms = (perf_counter() - started_at) * 1000
        log_command_event(
            "command_failed",
            command=command,
            status="error",
            error_code="AUTOCAD_PLUGIN_TIMEOUT",
            duration_ms=duration_ms,
        )
        return error_response(
            504,
            "AUTOCAD_PLUGIN_TIMEOUT",
            str(error),
            command=command,
        )
    except (ValueError, ContractValidationError) as error:
        duration_ms = (perf_counter() - started_at) * 1000
        error_code = (
            error.code
            if isinstance(error, ContractValidationError)
            else "INVALID_PLUGIN_RESPONSE"
        )
        log_command_event(
            "command_failed",
            command=command,
            status="error",
            error_code=error_code,
            duration_ms=duration_ms,
        )
        return error_response(
            502,
            error_code,
            str(error),
            command=command,
        )

    duration_ms = (perf_counter() - started_at) * 1000
    log_command_event(
        "command_completed",
        command=command,
        status=result.get("status", "success"),
        duration_ms=duration_ms,
    )
    return result
