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
        assert payload["schema_version"] == "0.2"
        assert payload["run_id"].startswith("run-")
        assert payload["command_id"].startswith("cmd-")
        assert payload["import_id"] is None
        assert payload["submitted_at"]
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


@pytest.mark.anyio
async def test_drawing_context_tool_emits_v03_read_command(
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
        assert payload["schema_version"] == "0.3"
        assert payload["operation"] == "get_drawing_context"
        assert payload["parameters"] == {}
        assert payload["requires_approval"] is False
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.get_drawing_context()

    assert result["status"] == "success"


@pytest.mark.anyio
async def test_create_line_forwards_optional_import_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        assert payload["import_id"] == "import-test-001"
        return {"status": "success"}

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
        units="inches",
        import_id="import-test-001",
    )

    assert result["status"] == "success"


@pytest.mark.anyio
async def test_window_tool_forwards_world_space_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        assert payload["operation"] == "get_entities_in_window"
        assert payload["coordinate_system"] == "world"
        assert payload["parameters"]["window_min"] == {
            "x": 1,
            "y": 2,
            "z": 0,
        }
        assert payload["parameters"]["window_max"] == {
            "x": 10,
            "y": 20,
            "z": 0,
        }
        assert payload["parameters"]["limit"] == 25
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    result = await odysseus_mcp.get_entities_in_window(
        min_x=1,
        min_y=2,
        max_x=10,
        max_y=20,
        limit=25,
    )

    assert result["status"] == "success"


@pytest.mark.anyio
async def test_entity_and_import_lookup_tools_forward_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[dict[str, Any]] = []

    async def fake_request_bridge(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert payload is not None
        commands.append(payload)
        return {"status": "success"}

    monkeypatch.setattr(
        odysseus_mcp,
        "request_bridge",
        fake_request_bridge,
    )

    await odysseus_mcp.get_entity_properties("2AF")
    await odysseus_mcp.find_entities_by_import_id("import-001", limit=20)

    assert commands[0]["parameters"] == {"object_id": "2AF"}
    assert commands[1]["parameters"] == {
        "target_import_id": "import-001",
        "limit": 20,
    }
