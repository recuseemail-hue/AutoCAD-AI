from typing import Any

import httpx
import pytest

from backend.src import odysseus_mcp


def test_docker_host_is_allowed() -> None:
    assert "host.docker.internal:*" in (
        odysseus_mcp.MCP_TRANSPORT_SECURITY.allowed_hosts
    )


@pytest.mark.anyio
async def test_bridge_health_tool_calls_http_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert method == "GET"
        assert path == "/health"
        assert payload is None
        return {
            "status": "ok",
            "service": "AutoCAD-AI bridge",
        }

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.get_bridge_health()

    assert result["status"] == "ok"


@pytest.mark.anyio
async def test_unavailable_bridge_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailableClient:
        async def __aenter__(self) -> "UnavailableClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def request(
            self,
            method: str,
            path: str,
            json: dict[str, Any] | None = None,
        ) -> httpx.Response:
            request = httpx.Request(method, f"http://127.0.0.1:8000{path}")
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(
        odysseus_mcp.httpx,
        "AsyncClient",
        lambda **kwargs: UnavailableClient(),
    )

    result = await odysseus_mcp.request_bridge("GET", "/health")

    assert result["status"] == "error"
    assert result["error"]["code"] == "BRIDGE_UNAVAILABLE"


@pytest.mark.anyio
async def test_create_line_requires_and_forwards_supported_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/commands"
        assert payload is not None
        assert payload["units"] == "centimeters"
        return {
            "command_id": payload["command_id"],
            "status": "success",
        }

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.create_autocad_line(
        start_x=0,
        start_y=0,
        end_x=10,
        end_y=0,
        units="centimeters",
    )

    assert result["status"] == "success"
