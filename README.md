# AutoCAD-AI

AutoCAD-AI is an AI-assisted design platform that connects a conversational interface to professional CAD, BIM, and engineering applications through controlled, structured commands.

The first target workflow uses **Odysseus** as the chat interface, a local **Python bridge** for validation and routing, and an **AutoCAD 2027 plugin** for native drawing operations. Revit, AutoSPRINK, PDF and image interpretation, and 3D modeling are planned after the AutoCAD connection is reliable.

## Current Status

Last updated: July 22, 2026.

The first live drawing vertical slice is complete: Odysseus successfully
created a native line through the MCP server, bridge, and AutoCAD plugin. Work
on branch `Luke/PDFRead` now adds the traceable v0.2 contract required for
reviewable PDF-to-CAD workflows.

| Component | Status | Verified result |
|---|---|---|
| JSON schemas v0.1 and v0.2 | Implemented | v0.1 remains compatible; v0.2 adds lifecycle identity and formal result/error contracts |
| FastAPI bridge v0.2.0 | Implemented | Validates by schema version, normalizes results, and returns traceable structured errors |
| AutoCAD connection reporting | Implemented | `GET /applications` reports plugin version and supported schema versions |
| Command observability | Implemented | Privacy-conscious JSONL logs correlate run, import, and command IDs |
| Odysseus MCP server | Working | Odysseus discovers all 3 tools through Streamable HTTP |
| AutoCAD 2027 plugin v0.2.0 | Implemented | Hosts local HTTP health and command endpoints on port `8765` |
| Live schema-v0.1 line creation | Verified | A real native AutoCAD line was created successfully |
| Live schema-v0.2 line creation | Pending reload check | Rebuilt DLL is ready for one final in-AutoCAD contract verification |

The verified baseline path is:

```text
User
  -> Odysseus Agent mode
  -> AutoCAD-AI MCP server (port 8001)
  -> FastAPI bridge (port 8000)
  -> AutoCAD 2027 plugin (port 8765)
  -> native AutoCAD line
  -> correlated command result
  -> Odysseus response
```

## Current MCP Tools

The Odysseus integration currently exposes:

- `get_bridge_health` - confirms that the local Python bridge is available.
- `get_autocad_status` - reports whether an AutoCAD plugin is connected.
- `create_autocad_line` - builds a traceable schema-v0.2 line command and submits it to the bridge.

All three tools have been verified on the v0.1 baseline. The rebuilt v0.2
plugin requires one live reload check before Milestone 1 is closed.

## Local Service Addresses

| Service | Address |
|---|---|
| FastAPI bridge | `http://127.0.0.1:8000` |
| Bridge health | `http://127.0.0.1:8000/health` |
| Application status | `http://127.0.0.1:8000/applications` |
| AutoCAD plugin command endpoint | `http://localhost:8765/command` |
| AutoCAD plugin health endpoint | `http://localhost:8765/health` |
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

## Milestone 1 Configuration

Defaults are centralized in `backend/src/config.py` and can be overridden with:

| Environment variable | Default |
|---|---|
| `AUTOCAD_AI_PLUGIN_URL` | `http://localhost:8765` |
| `AUTOCAD_AI_PLUGIN_HEALTH_TIMEOUT_SECONDS` | `2.0` |
| `AUTOCAD_AI_PLUGIN_COMMAND_TIMEOUT_SECONDS` | `35.0` |
| `AUTOCAD_AI_BRIDGE_URL` | `http://127.0.0.1:8000` |
| `AUTOCAD_AI_BRIDGE_TIMEOUT_SECONDS` | `40.0` |
| `AUTOCAD_AI_LOG_PATH` | `backend/output/autocad-ai.jsonl` |
| `AUTOCAD_AI_LOG_MAX_BYTES` | `5242880` |
| `AUTOCAD_AI_LOG_BACKUP_COUNT` | `3` |

The command log records lifecycle metadata, not complete geometry payloads.

## Immediate Next Step

Verify the newly rebuilt v0.2 contract in AutoCAD:

1. Load `Plugin/AutoCadAIPlugin/dist/AutoCadAIPlugin.dll` in AutoCAD 2027.
2. Verify `http://localhost:8765/health` directly.
3. Verify that `get_autocad_status` reports connected.
4. Ask Odysseus to create one line with explicit coordinates, units, and layer.
5. Confirm that the result includes matching `run_id` and `command_id`,
   bridge/plugin versions, timestamps, active document, and object handle.
6. Undo the operation safely, then begin Milestone 2 read-only tools.

## Design Principles

- AI interprets intent; deterministic application code executes geometry.
- Commands are structured, versioned, and validated before execution.
- Read application state before making changes whenever practical.
- Destructive, ambiguous, and engineering-sensitive actions require human approval.
- Every command should return a clear result and remain traceable.
- Application adapters stay separate so AutoCAD, Revit, and AutoSPRINK can evolve independently.
- Plugin and bridge contract changes are coordinated and versioned together.

## Repository Layout

```text
AutoCAD-AI/
|-- backend/
|   |-- src/
|   |   |-- api.py
|   |   |-- config.py
|   |   |-- connection_manager.py
|   |   |-- contracts.py
|   |   |-- observability.py
|   |   `-- odysseus_mcp.py
|   `-- tests/
|-- docs/
|   |-- architecture.md
|   `-- roadmap.md
|-- examples/
|-- Plugin/                  # AutoCAD 2027 plugin
|-- schemas/
|   |-- v0.1/
|   `-- v0.2/
|-- Implementation Plan.md
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

See [Implementation Plan](Implementation%20Plan.md) for the PDF-to-CAD
delivery plan, [Architecture](docs/architecture.md) for system boundaries, and
[Roadmap](docs/roadmap.md) for project history.
