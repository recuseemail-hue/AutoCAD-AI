# AutoCAD-AI Architecture

Last updated: July 21, 2026.

## 1. Product Vision

AutoCAD-AI is a controlled AI design platform that allows a user to communicate with CAD, BIM, and specialized engineering applications through conversation.

The first implementation uses:

- **Odysseus** as the user-facing AI chat interface;
- an **MCP server** that exposes narrow AutoCAD-AI tools to Odysseus;
- a local **Python/FastAPI bridge** that validates and routes commands;
- a teammate-owned **AutoCAD 2027 plugin** that executes native AutoCAD operations.

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
        | WebSocket: /ws/autocad
        v
AutoCAD 2027 plugin (not connected yet)
        |
        v
AutoCAD drawing database
```

The portion through the FastAPI bridge has been verified from Odysseus. The bridge correctly reports that AutoCAD is currently disconnected. The plugin-to-bridge and live drawing-operation portion remains the next integration boundary.

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
| `create_autocad_line` | `POST /commands` | Defined; live AutoCAD execution not yet verified |

The server returns structured errors when the bridge cannot be reached or returns an unsuccessful HTTP response.

### 3.3 FastAPI Bridge

Files:

- `backend/src/api.py`
- `backend/src/connection_manager.py`

The bridge is the application broker between AI-facing tools and application plugins.

Current endpoints:

| Endpoint | Purpose | Current behavior |
|---|---|---|
| `GET /health` | Service health | Returns that the bridge is running |
| `GET /applications` | Application status | Reports the live AutoCAD WebSocket state |
| `POST /commands` | Submit a validated command | Rejects malformed commands and returns `503` when AutoCAD is disconnected |
| `WS /ws/autocad` | Plugin transport | Accepts one AutoCAD client connection |

The bridge currently validates incoming commands using schema v0.1. It no longer returns a successful mock result when AutoCAD is unavailable.

The remaining bridge gap is command-result correlation. `connection_manager.py` must:

1. create a pending result for each `command_id`;
2. send the command to the connected WebSocket client;
3. wait for the matching plugin response;
4. resolve the correct pending HTTP request;
5. handle timeouts, disconnects, duplicate IDs, and malformed results;
6. clean up pending state on every success and failure path.

### 3.4 Command Schema

File: `schemas/v0.1/command.schema.json`

The command schema is the shared contract between Odysseus tools, the bridge, and application plugins.

The current v0.1 contract supports one operation:

```text
create_line
```

Example:

```json
{
  "schema_version": "0.1",
  "command_id": "cmd-001",
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

The schema requires explicit coordinates, units, layer behavior, application target, operation name, and command identity. Unsupported or incomplete commands must be rejected rather than guessed.

### 3.5 AutoCAD 2027 Plugin

Directory: `Plugin/`

The AutoCAD plugin is maintained by the user's teammate and is outside the backend work boundary.

Intended responsibilities:

- connect to `ws://127.0.0.1:8000/ws/autocad`;
- receive validated command messages;
- marshal work onto a valid AutoCAD application/document context;
- perform native AutoCAD transactions;
- validate units, geometry, document state, and layers independently;
- return a structured result with the original `command_id`;
- group changes so they can be undone safely;
- reconnect and shut down cleanly.

The Python backend must not depend on the plugin's internal classes. Both sides depend only on the agreed network message contract.

## 4. Command Lifecycle

### 4.1 Current read-only lifecycle

This path is working:

```text
1. User asks Odysseus to check bridge or AutoCAD status.
2. Odysseus calls the corresponding MCP tool.
3. The MCP server sends an HTTP request to the bridge.
4. The bridge reads its live state.
5. The result returns through MCP to Odysseus.
```

### 4.2 Target write lifecycle

This path is not complete yet:

```text
1. User asks Odysseus to create a line.
2. Odysseus calls create_autocad_line with explicit values.
3. The MCP server builds a schema-v0.1 command.
4. The bridge validates the command.
5. The bridge stores a pending result under command_id.
6. The bridge sends the command to the AutoCAD plugin over WebSocket.
7. The plugin validates and executes the operation in AutoCAD.
8. The plugin returns a command_result containing the same command_id.
9. The bridge resolves the pending HTTP request.
10. MCP returns the actual AutoCAD result to Odysseus.
```

## 5. Response Contract Direction

A final response schema still needs to be formalized. The target shape is:

```json
{
  "message_type": "command_result",
  "schema_version": "0.1",
  "command_id": "cmd-001",
  "application": "autocad",
  "status": "success",
  "result": {
    "document": "Drawing1.dwg",
    "affected_objects": [
      {
        "type": "LINE",
        "handle": "2F7",
        "layer": "AI-WALL",
        "action": "created"
      }
    ]
  },
  "warnings": [],
  "error": null
}
```

The final contract must define successful, warning, rejected, timeout, disconnected, and execution-error states.

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
- `get_autocad_status` reaches the bridge and accurately reports disconnected.
- The bridge's WebSocket endpoint can accept a test connection.
- A command can be sent from the bridge to a browser-based test WebSocket client.

Automated tests currently show:

- MCP transport-security and bridge-error tests pass.
- Invalid command validation passes.
- Two older API assertions still describe the retired mock behavior and must be updated:
  - the health test expects the old service name `AutoCAD-AI mock bridge`;
  - the valid-command test expects a fake success even without AutoCAD, while the live bridge correctly returns `503`.

These failing assertions are documentation debt in the test suite, not evidence that the verified health/status integration is broken.

## 8. Ownership and Change Boundaries

| Area | Owner for current work |
|---|---|
| `backend/`, MCP integration, schemas, backend tests | User and Codex collaboration |
| `Plugin/` AutoCAD code | Teammate |
| Shared WebSocket and command-result contract | Team agreement |

Backend changes must not modify `Plugin/` unless the user explicitly changes this boundary.

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

The initial infrastructure milestone is complete only when:

1. AutoCAD 2027 reports connected through Odysseus.
2. Odysseus submits one explicit `create_line` tool call.
3. The bridge validates and forwards it to the real plugin.
4. The plugin creates the native line in the intended drawing and layer.
5. The plugin returns the real object identifier and command result.
6. The bridge correlates that result with the original request.
7. Odysseus reports the actual result rather than a mock response.
8. The action can be undone safely.
