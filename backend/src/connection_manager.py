import os
from typing import Any

import httpx


PLUGIN_URL = os.getenv(
    "AUTOCAD_AI_PLUGIN_URL",
    "http://localhost:8765",
).rstrip("/")

PLUGIN_HEALTH_TIMEOUT_SECONDS = 2.0
PLUGIN_COMMAND_TIMEOUT_SECONDS = 35.0


class AutoCADPluginHTTPError(Exception):
    """Represent a structured unsuccessful response from the AutoCAD plugin."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        message = body.get(
            "message",
            f"AutoCAD plugin returned HTTP {status_code}.",
        )
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AutoCADPluginClient:
    """Call the local HTTP endpoint hosted by the loaded AutoCAD plugin."""

    def __init__(
        self,
        base_url: str = PLUGIN_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    async def is_connected(self) -> bool:
        """Return true only when the plugin responds with its expected health payload."""

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=PLUGIN_HEALTH_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.get("/health")
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError):
            return False

        return (
            isinstance(body, dict)
            and body.get("status") == "ok"
            and body.get("application") == "autocad"
        )

    async def send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send one validated command and return the plugin's correlated result."""

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=PLUGIN_COMMAND_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.post("/command", json=command)
        except httpx.TimeoutException as error:
            raise TimeoutError(
                "The AutoCAD plugin did not return a command result in time."
            ) from error
        except httpx.RequestError as error:
            raise RuntimeError(
                f"Could not reach the AutoCAD plugin at {self.base_url}."
            ) from error

        try:
            body = response.json()
        except ValueError as error:
            raise ValueError("The AutoCAD plugin returned a non-JSON response.") from error

        if not isinstance(body, dict):
            raise ValueError("The AutoCAD plugin response was not a JSON object.")

        if response.is_error:
            raise AutoCADPluginHTTPError(response.status_code, body)

        expected_command_id = command.get("command_id")
        if body.get("command_id") != expected_command_id:
            raise ValueError(
                "The AutoCAD plugin response command_id did not match the request."
            )

        return body


autocad_plugin_client = AutoCADPluginClient()
