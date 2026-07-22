# AutoCAD-AI

AutoCAD-AI is an AI-assisted design platform that connects a conversational interface to professional CAD, BIM, and engineering applications through controlled, structured commands.

The first target workflow uses **Odysseus** as the chat interface, a local **Python bridge** for validation and routing, and an **AutoCAD 2027 plugin** for native drawing operations. Revit, AutoSPRINK, PDF and image interpretation, and 3D modeling are planned after the AutoCAD connection is reliable.

## Current Status

Last updated: July 21, 2026.

The project has moved beyond the original in-process mock response. Odysseus can now discover and call the project's MCP tools, and those tools can reach the live Python bridge.

| Component | Status | Verified result |
|---|---|---|
| JSON command schema v0.1 | Working baseline | Valid `create_line` requests are accepted and malformed requests are rejected |
| FastAPI bridge | Running | `GET /health` returns `status: ok` |
| AutoCAD connection reporting | Running | `GET /applications` reports the live connection state |
| AutoCAD WebSocket endpoint | Partial | The bridge accepts a client at `/ws/autocad`; full command-result correlation still needs completion |
| Odysseus MCP server | Working | Odysseus discovers all 3 tools through Streamable HTTP |
| Odysseus to bridge health check | Verified | `get_bridge_health` returned that the bridge is running and healthy |
| Odysseus to AutoCAD status check | Verified | `get_autocad_status` correctly reported that AutoCAD is not connected |
| AutoCAD 2027 plugin | Teammate-owned, in progress | Waiting for the plugin to connect to the Python bridge |
| Live line creation in AutoCAD | Not yet verified | Blocked until the plugin is connected and command responses are correlated |

The current verified path is:

```text
User
  -> Odysseus Agent mode
  -> AutoCAD-AI MCP server (port 8001)
  -> FastAPI bridge (port 8000)
  -> connection-status result
  -> Odysseus response
```

The next complete path will be:

```text
User
  -> Odysseus Agent mode
  -> MCP tool call
  -> FastAPI bridge
  -> WebSocket command
  -> AutoCAD 2027 plugin
  -> native AutoCAD operation
  -> correlated command result
  -> Odysseus response
```

## Current MCP Tools

The Odysseus integration currently exposes:

- `get_bridge_health` - confirms that the local Python bridge is available.
- `get_autocad_status` - reports whether an AutoCAD plugin is connected.
- `create_autocad_line` - builds a schema-v0.1 line command and submits it to the bridge.

The first two tools have been verified from Odysseus. `create_autocad_line` must not be treated as complete until AutoCAD is connected and the result is returned from the real plugin.

## Local Service Addresses

| Service | Address |
|---|---|
| FastAPI bridge | `http://127.0.0.1:8000` |
| Bridge health | `http://127.0.0.1:8000/health` |
| Application status | `http://127.0.0.1:8000/applications` |
| AutoCAD WebSocket | `ws://127.0.0.1:8000/ws/autocad` |
| MCP server | `http://127.0.0.1:8001/mcp` |
| MCP URL used by Dockerized Odysseus | `http://host.docker.internal:8001/mcp` |
| Odysseus web interface | `http://localhost:7000` |

## Running the Current Backend

From the repository root, activate the virtual environment and start the bridge:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.src.api:app --reload --port 8000
```

In a second terminal, activate the same environment and start the MCP server:

```powershell
.\.venv\Scripts\Activate.ps1
python -m backend.src.odysseus_mcp
```

Odysseus should use the Streamable HTTP MCP URL:

```text
http://host.docker.internal:8001/mcp
```

Use **Agent mode** when calling MCP tools. The current Odysseus OpenAI integration sends agent tools through Chat Completions. `gpt-4.1` has been used as the compatible model for these tests; `gpt-5.6-sol` currently produces a reasoning-effort/tool incompatibility until Odysseus supports the appropriate Responses API path or explicitly disables reasoning effort for that request.

## Immediate Next Milestone

Complete one real, reversible AutoCAD operation:

1. Finish command-result correlation in the Python connection manager.
2. Update the backend tests to describe the live bridge instead of the retired mock behavior.
3. Load the teammate-owned plugin in AutoCAD 2027.
4. Connect it to `ws://127.0.0.1:8000/ws/autocad`.
5. Verify that `get_autocad_status` reports connected.
6. Ask Odysseus to create one line with explicit coordinates, units, and layer.
7. Return the real AutoCAD result to Odysseus.
8. Verify that the created operation can be undone safely.

## Design Principles

- AI interprets intent; deterministic application code executes geometry.
- Commands are structured, versioned, and validated before execution.
- Read application state before making changes whenever practical.
- Destructive, ambiguous, and engineering-sensitive actions require human approval.
- Every command should return a clear result and remain traceable.
- Application adapters stay separate so AutoCAD, Revit, and AutoSPRINK can evolve independently.
- The teammate-owned `Plugin/` code is not modified by backend work without coordination.

## Repository Layout

```text
AutoCAD-AI/
|-- backend/
|   |-- src/
|   |   |-- api.py
|   |   |-- connection_manager.py
|   |   |-- mock_backend.py
|   |   `-- odysseus_mcp.py
|   `-- tests/
|-- docs/
|   |-- architecture.md
|   `-- roadmap.md
|-- examples/
|-- Plugin/                  # Teammate-owned AutoCAD 2027 plugin
|-- schemas/
|   `-- v0.1/
|-- README.md
|-- requirements.txt
`-- requirements-odysseus.txt
```

## Long-Term Direction

After the first AutoCAD vertical slice is dependable, the platform may expand to:

- additional 2D AutoCAD operations and compound drafting workflows;
- reading and modifying existing drawing geometry;
- PDF and image interpretation with user-reviewed geometry;
- native Revit elements and BIM workflows;
- basic 3D reconstruction from structured instructions and plans;
- supported AutoSPRINK operations and deterministic fire-protection checks;
- multi-application coordination through the same versioned command platform.

See [Architecture](docs/architecture.md) for system boundaries and [Roadmap](docs/roadmap.md) for milestones and current progress.
