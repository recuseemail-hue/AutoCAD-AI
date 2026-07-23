# AutoCAD-AI Architecture

Last updated: July 23, 2026.

## 1. Product Vision

AutoCAD-AI is a controlled AI design platform that allows a user to communicate with CAD, BIM, and specialized engineering applications through conversation.

The first implementation uses:

- **Odysseus** as the user-facing AI chat interface;
- an **MCP server** that exposes narrow AutoCAD-AI tools to Odysseus;
- a local **Python/FastAPI bridge** that validates and routes commands;
- an **AutoCAD 2027 plugin** that executes native AutoCAD operations.

The platform is intended to support Revit, AutoSPRINK, image and PDF interpretation, and 3D workflows later. Those capabilities must reuse the shared command and safety architecture instead of embedding application-specific behavior into the AI prompt.

## 2. Current Verified Architecture

```text
Odysseus web UI (Docker, port 7000)
        |
        | MCP Streamable HTTP
        v
AutoCAD-AI MCP server (host port 8001)
        |
        | local HTTP
        v
FastAPI bridge (host port 8000)
        |
        | local HTTP: port 8765
        v
AutoCAD 2027 plugin
        |
        v
AutoCAD drawing database
```

The complete v0.2 path has been verified with a native line created in
AutoCAD. Schema v0.3 preserves that contract while adding
traceable run identity, formal results and errors, version reporting, document
identity, timestamps, privacy-conscious lifecycle logs, and bounded read-only
drawing inspection.

## 3. Component Responsibilities

### 3.1 Odysseus

Odysseus is the initial conversational interface.

Responsibilities:

- accept user requests;
- select the appropriate MCP tool;
- ask for missing information;
- display connection state, results, warnings, and errors;
- request approval for high-impact operations;
- maintain conversation context.

Odysseus must not directly manipulate AutoCAD or invent unvalidated drawing operations.

Current integration details:

- Odysseus runs in Docker and is available at `http://localhost:7000`.
- It connects to the MCP server at `http://host.docker.internal:8001/mcp`.
- MCP tools must be called in Agent mode.
- `gpt-4.1` is the currently verified Chat Completions-compatible tool model.
- `gpt-5.6-sol` cannot currently combine its reasoning effort with function tools through Odysseus's `/v1/chat/completions` path. Supporting it requires a future Responses API integration or a compatible no-reasoning request setting.

### 3.2 MCP Server

File: `backend/src/odysseus_mcp.py`

The MCP server translates narrow AI tool calls into HTTP requests to the local bridge. It uses Streamable HTTP and listens on host port `8001`.

Current tools:

| Tool | Bridge request | Status |
|---|---|---|
| `get_bridge_health` | `GET /health` | Verified from Odysseus |
| `get_autocad_status` | `GET /applications` | Verified from Odysseus |
| `create_autocad_line` | `POST /commands` | Live v0.1 path verified; now emits v0.2 |
| Drawing context tools (5) | `POST /commands` | Emit schema-v0.3 read commands |
| Layer and entity tools (5) | `POST /commands` | Emit bounded schema-v0.3 read commands |

The server returns structured errors when the bridge cannot be reached or returns an unsuccessful HTTP response.

### 3.3 FastAPI Bridge

Files:

- `backend/src/api.py`
- `backend/src/config.py`
- `backend/src/connection_manager.py`
- `backend/src/contracts.py`
- `backend/src/observability.py`

The bridge is the application broker between AI-facing tools and application plugins.

Current endpoints:

| Endpoint | Purpose | Current behavior |
|---|---|---|
| `GET /health` | Service health | Reports bridge version and supported schemas |
| `GET /applications` | Application status | Reports plugin health, version, and supported schemas |
| `POST /commands` | Submit a validated command | Validates v0.1/v0.2, forwards, correlates, normalizes, and logs the result |

The bridge selects a contract by `schema_version`. Schema v0.1 remains
supported for compatibility; schema v0.2 is the current MCP contract.

HTTP request/response semantics provide command-result correlation. `connection_manager.py` checks that a successful plugin response contains the same `command_id`, maps connection failures to `503`, maps timeouts to `504`, rejects malformed responses, and preserves structured plugin errors.

### 3.4 Network Contracts

Files:

- `schemas/v0.1/command.schema.json`
- `schemas/v0.2/command.schema.json`
- `schemas/v0.2/result.schema.json`
- `schemas/v0.2/error.schema.json`
- `schemas/v0.3/command.schema.json`
- `schemas/v0.3/result.schema.json`
- `schemas/v0.3/error.schema.json`

These schemas are the shared contract between Odysseus tools, the bridge, and
application plugins. Schemas v0.1 and v0.2 support:

```text
create_line
```

The v0.2 request adds lifecycle identity:

```json
{
  "schema_version": "0.2",
  "run_id": "run-001",
  "import_id": null,
  "command_id": "cmd-001",
  "submitted_at": "2026-07-22T18:30:00Z",
  "application": "autocad",
  "operation": "create_line",
  "parameters": {
    "start": {"x": 0, "y": 0, "z": 0},
    "end": {"x": 20, "y": 0, "z": 0},
    "layer": "AI-WALL",
    "create_layer_if_missing": true
  },
  "units": "feet",
  "coordinate_system": "world",
  "requires_approval": false
}
```

The schema requires explicit coordinates, units, layer behavior, application
target, operation name, and command identity. Unsupported or incomplete
commands are rejected rather than guessed.

Schema v0.3 freezes line creation at v0.2 and adds ten read-only operations.
Each operation has an explicit parameter shape. Layer and entity collections
are capped at 500 records, window queries require world coordinates, and
handle lookups accept only hexadecimal AutoCAD handles.

### 3.5 AutoCAD 2027 Plugin

Directory: `Plugin/`

The AutoCAD plugin owns native execution. Its internal AutoCAD implementation
stays isolated from the backend, while its network contract is coordinated
with the bridge.

Current responsibilities:

- host `GET http://localhost:8765/health` and `POST http://localhost:8765/command`;
- receive validated command messages over local HTTP;
- marshal work onto a valid AutoCAD application/document context;
- perform native AutoCAD transactions;
- validate units, geometry, document state, and layers independently;
- return a structured result with the original `command_id`;
- group changes so they can be undone safely;
- start when loaded and shut down cleanly.

The Python backend must not depend on the plugin's internal classes. Both sides depend only on the agreed network message contract.

## 4. Command Lifecycle

### 4.1 Read-only lifecycle

This path is working:

```text
1. User asks Odysseus about the active drawing, layers, or entities.
2. Odysseus calls one narrow read-only MCP tool.
3. The MCP server builds a traceable schema-v0.3 command.
4. The bridge validates and forwards the command.
5. The plugin opens AutoCAD objects in read mode on the UI thread.
6. The result is normalized, schema-validated, logged, and returned.
```

### 4.2 Write lifecycle

This path is implemented:

```text
1. User asks Odysseus to create a line.
2. Odysseus calls create_autocad_line with explicit values.
3. The MCP server builds a schema-v0.2 command with lifecycle IDs.
4. The bridge validates the command.
5. The bridge checks the plugin's health endpoint.
6. The bridge posts the command to the AutoCAD plugin over local HTTP.
7. The plugin queues the work for AutoCAD's UI thread, validates it, and executes it.
8. The plugin returns a structured result containing the same lifecycle IDs.
9. The bridge verifies and normalizes the result against the v0.2 schema.
10. MCP returns the actual AutoCAD result to Odysseus.
```

## 5. Response and Error Contracts

Successful v0.2 commands return a schema-validated result:

```json
{
  "schema_version": "0.2",
  "run_id": "run-001",
  "import_id": null,
  "command_id": "cmd-001",
  "application": "autocad",
  "operation": "create_line",
  "status": "success",
  "message": "Line created successfully.",
  "error": null,
  "affected_objects": [
    {
      "object_type": "LINE",
      "object_id": "2F7",
      "action": "created"
    }
  ],
  "data": {
    "layer": "AI-WALL",
    "start_in_drawing_units": [0, 0, 0],
    "end_in_drawing_units": [20, 0, 0]
  },
  "undo_token": "ai-action-001",
  "warnings": [],
  "document": {
    "name": "Drawing1.dwg"
  },
  "versions": {
    "bridge": "0.2.0",
    "plugin": "0.2.0"
  },
  "timestamps": {
    "submitted_at": "2026-07-22T18:30:00Z",
    "bridge_received_at": "2026-07-22T18:30:00.100Z",
    "completed_at": "2026-07-22T18:30:00.250Z"
  }
}
```

Bridge failures use the formal error schema with a stable code, message,
lifecycle IDs when known, and bridge timestamp. Plugin
failures are normalized into the same v0.2 result envelope.

## 6. Safety and Trust Boundaries

### AI boundary

The model may interpret intent and select a tool. It is not trusted for precise geometry, unit conversion, document locking, transactions, or code compliance.

### MCP boundary

MCP tools expose narrow operations rather than unrestricted shell or AutoCAD API access. Tool arguments must remain explicit and schema-compatible.

### Bridge boundary

The bridge validates commands, checks application availability, enforces timeouts, correlates results, and returns structured failures. Local-only networking is the current default.

### Plugin boundary

The plugin must independently validate every command because bridge validation alone is not a security boundary. It owns AutoCAD document locks, transactions, object identifiers, undo grouping, and native API correctness.

### Human approval boundary

Deletion, bulk modification, ambiguous selection, unit changes, engineering assumptions, and safety-critical domain operations require explicit approval before execution.

## 7. Testing Status

Verified manually:

- Odysseus discovers all three MCP tools.
- `get_bridge_health` reaches the bridge and returns healthy.
- `get_autocad_status` reaches the bridge and reports live connection state.
- A complete v0.1 `create_autocad_line` call created a native AutoCAD line.
- A complete v0.2 `create_autocad_line` call completed with correlated
  lifecycle IDs.
- The HTTP plugin adapter detects connected and disconnected health states in automated tests.
- Validated commands are posted to `/command` and correlated by `command_id` in automated tests.

Automated tests currently show:

- MCP transport-security and bridge-error tests pass.
- Invalid command validation passes.
- Backend API tests cover health, plugin status, disconnected commands, successful real-result forwarding, structured plugin errors, and schema validation.
- Contract tests cover v0.1 compatibility, v0.2 commands, normalized v0.2
  results, structured errors, settings, lifecycle correlation, and log safety.
- Schema-v0.3 tests cover all ten read operations, bounded parameters, bridge
  normalization, and MCP argument mapping.

## 8. Ownership and Change Boundaries

| Area | Owner for current work |
|---|---|
| `backend/`, MCP integration, schemas, backend tests | User and Codex collaboration |
| `Plugin/` AutoCAD code | Team, with explicit contract coordination |
| Shared HTTP command-result contract | Team agreement |

Plugin changes in Milestone 1 were explicitly authorized so both sides expose
the same v0.2 network contract.

## 9. Future Application Adapters

After the first AutoCAD vertical slice is stable, the same architecture can add separate adapters:

```text
Shared Odysseus tools and command platform
        |-- AutoCAD adapter
        |-- Revit adapter
        |-- AutoSPRINK adapter
        `-- future CAD/BIM adapters
```

Each adapter should use native application objects and transactions while sharing versioning, identity, validation, approvals, logging, and result semantics.

## 10. First End-to-End Definition of Done

The initial v0.1 infrastructure milestone is complete:

1. AutoCAD 2027 reports connected through Odysseus.
2. Odysseus submits one explicit `create_line` tool call.
3. The bridge validates and forwards it to the real plugin.
4. The plugin creates the native line in the intended drawing and layer.
5. The plugin returns the real object identifier and command result.
6. The bridge correlates that result with the original request.
7. Odysseus reports the actual result rather than a mock response.
8. The action can be undone safely.
