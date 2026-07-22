# AutoCAD-AI Roadmap

Last updated: July 21, 2026.

## Status Legend

- **Complete** - implemented and verified.
- **Active** - currently being built or corrected.
- **Waiting** - dependent on teammate work or an external condition.
- **Planned** - intentionally deferred until earlier infrastructure works.

## Current Milestone

The project is building its first real vertical slice:

> A user asks Odysseus to create one line; the request travels through MCP and the Python bridge to the AutoCAD 2027 plugin; AutoCAD creates the line; the actual result returns to Odysseus; and the operation can be undone safely.

The Odysseus-to-bridge portion is working. The AutoCAD plugin is not yet connected, so the complete line-creation path has not been verified.

## Progress Summary

| Area | Status |
|---|---|
| Repository and Python environment | Complete |
| Command schema v0.1 for `create_line` | Complete baseline |
| FastAPI health and command validation | Complete baseline |
| AutoCAD connection-status endpoint | Complete |
| WebSocket endpoint for AutoCAD | Partial |
| MCP server and three Odysseus tools | Complete baseline |
| Odysseus MCP discovery | Complete: 3/3 tools |
| Odysseus bridge-health tool call | Complete |
| Odysseus AutoCAD-status tool call | Complete |
| Command-result correlation | Active |
| Backend test alignment after mock removal | Active |
| AutoCAD 2027 plugin connection | Waiting on teammate |
| Real AutoCAD line creation | Waiting |
| Undo of an AI operation | Waiting |

## Phase 1 - Foundation

Status: **Complete**

- [x] Create the GitHub repository.
- [x] Create the Python virtual environment.
- [x] Install initial Python dependencies.
- [x] Add `requirements.txt`.
- [x] Add `.gitignore` rules for local environments and caches.
- [x] Create the backend, tests, schema, examples, and documentation areas.
- [x] Establish AutoCAD 2027 as the first target application.
- [x] Separate teammate-owned plugin work from backend work.

## Phase 2 - Structured Command Contract

Status: **Complete baseline**

- [x] Create `schemas/v0.1/command.schema.json`.
- [x] Define the `create_line` request.
- [x] Require a command ID, application, operation, parameters, units, coordinate system, and approval flag.
- [x] Add valid request and success-response examples.
- [x] Verify valid JSON loading.
- [x] Verify that a command missing its endpoint is rejected.
- [ ] Create a formal response schema.
- [ ] Define response statuses and error codes.
- [ ] Define plugin registration and version compatibility messages.
- [ ] Add separate schemas for WebSocket envelopes and command results.

## Phase 3 - Live Python Bridge

Status: **Active**

Implemented:

- [x] Create the FastAPI application.
- [x] Add `GET /health`.
- [x] Add `GET /applications`.
- [x] Add validated `POST /commands`.
- [x] Return `422` for invalid commands.
- [x] Return `503` when AutoCAD is disconnected.
- [x] Add `WS /ws/autocad`.
- [x] Store the current AutoCAD WebSocket connection.
- [x] Detect WebSocket disconnection.
- [x] Send JSON commands to a connected test client.
- [x] Stop returning in-process mock success from the active API route.

Next backend work:

- [ ] Store a pending result by `command_id` before sending a command.
- [ ] Resolve the pending result when the matching plugin response arrives.
- [ ] Return the correlated result to the original HTTP caller.
- [ ] Add a command timeout and return `504` cleanly.
- [ ] Reject duplicate pending command IDs.
- [ ] Fail and clean pending requests when AutoCAD disconnects.
- [ ] Reject malformed or unknown plugin responses.
- [ ] Add structured bridge logging without exposing secrets.
- [ ] Decide whether local authentication is required before broader use.

## Phase 4 - Odysseus MCP Integration

Status: **Complete baseline**

- [x] Add `backend/src/odysseus_mcp.py`.
- [x] Use MCP Streamable HTTP on port `8001`.
- [x] Permit Dockerized Odysseus through `host.docker.internal`.
- [x] Add `get_bridge_health`.
- [x] Add `get_autocad_status`.
- [x] Add `create_autocad_line`.
- [x] Connect Odysseus using `http://host.docker.internal:8001/mcp`.
- [x] Verify that Odysseus discovers 3/3 tools.
- [x] Verify the bridge health tool from an Odysseus conversation.
- [x] Verify the AutoCAD status tool from an Odysseus conversation.
- [x] Confirm that the disconnected result accurately reflects bridge state.
- [ ] Verify `create_autocad_line` against the real plugin.
- [ ] Add tool descriptions and approval behavior for future operations.
- [ ] Add concise user-facing interpretations for common bridge errors.

Known model constraint:

- [x] Verify Agent mode with `gpt-4.1` through the current Chat Completions integration.
- [ ] Add Odysseus Responses API support, or an equivalent compatible setting, before relying on `gpt-5.6-sol` with tools and reasoning enabled.

## Phase 5 - Test Suite Alignment

Status: **Active**

Current verified automated results:

- [x] Invalid command validation passes.
- [x] MCP Docker-host allowance test passes.
- [x] MCP bridge-health forwarding test passes.
- [x] MCP unavailable-bridge structured-error test passes.

Required updates:

- [ ] Change the health test to expect `AutoCAD-AI bridge` instead of the retired `AutoCAD-AI mock bridge` label.
- [ ] Change the disconnected command test to expect `503` instead of a fake `200` success.
- [ ] Add an async WebSocket test client that returns a correlated command result.
- [ ] Test command timeout behavior.
- [ ] Test client disconnection during a pending command.
- [ ] Test duplicate and unexpected command results.
- [ ] Convert the example validation script into collected pytest functions if it should remain part of the suite.
- [ ] Resolve or deliberately pin the Starlette/httpx test-client deprecation warning.

## Phase 6 - AutoCAD 2027 Plugin Connection

Status: **Waiting on teammate**

The `Plugin/` directory is teammate-owned and is not modified by backend work.

Shared integration requirements:

- [ ] Build and load the plugin in AutoCAD 2027.
- [ ] Connect to `ws://127.0.0.1:8000/ws/autocad`.
- [ ] Report a stable plugin/application identity and version.
- [ ] Receive a schema-v0.1 `create_line` command.
- [ ] Marshal execution into a valid AutoCAD context.
- [ ] Validate drawing state, units, layer, and geometry independently.
- [ ] Execute the operation in a native AutoCAD transaction.
- [ ] Return a structured result with the original `command_id`.
- [ ] Include the active document and affected object handle.
- [ ] Group the operation so the user can undo it safely.
- [ ] Reconnect after AutoCAD or the bridge restarts.

Completion criteria:

> `get_autocad_status` reports connected from Odysseus while the real AutoCAD 2027 plugin is loaded.

## Phase 7 - First Real Drawing Operation

Status: **Waiting**

- [ ] Open a disposable AutoCAD test drawing.
- [ ] Confirm drawing units.
- [ ] Ask Odysseus to create one explicitly located line.
- [ ] Validate the command at the MCP and bridge boundaries.
- [ ] Create or select the requested layer safely.
- [ ] Create the native AutoCAD line.
- [ ] Return the actual document, layer, and object handle.
- [ ] Display the result in Odysseus.
- [ ] Undo the complete AI action once.
- [ ] Repeat the test after restarting the bridge and plugin.

Completion criteria:

> The full result comes from AutoCAD, not a browser test client or mock backend.

## Phase 8 - Read-Only AutoCAD Tools

Status: **Planned**

Read operations should precede broader write access.

- [ ] Get active document.
- [ ] Get document read-only state.
- [ ] Get drawing units.
- [ ] Get current UCS.
- [ ] Get current layer.
- [ ] List layers.
- [ ] Get selected objects.
- [ ] Get entity properties by stable identifier.
- [ ] Get drawing extents.

## Phase 9 - Primitive AutoCAD Operations

Status: **Planned**

- [ ] Create a layer.
- [ ] Create a polyline.
- [ ] Create a circle.
- [ ] Create an arc.
- [ ] Create text.
- [ ] Insert a known block.
- [ ] Move, copy, rotate, and change layer.
- [ ] Preview proposed targets before modification.
- [ ] Add approval for delete and bulk-edit operations.
- [ ] Group multi-entity requests into one undoable action.

Each operation requires a versioned schema, validation, plugin result, automated test, and recovery behavior before it is considered complete.

## Phase 10 - Compound 2D Drafting

Status: **Planned**

- [ ] Build rectangular room geometry.
- [ ] Create wall thickness with controlled offsets.
- [ ] Place door and window openings.
- [ ] Create repeated grids and block layouts.
- [ ] Add dimensions and notes.
- [ ] Detect duplicate, disconnected, or short geometry.
- [ ] Preview and approve compound operations.

Compound workflows must decompose into logged primitive commands.

## Phase 11 - Images and PDFs

Status: **Planned**

- [ ] Upload images and PDFs through the project interface.
- [ ] Prefer native/vector geometry when available.
- [ ] Rasterize scanned pages only when needed.
- [ ] Calibrate scale using confirmed reference points.
- [ ] Detect candidate lines, arcs, text, and symbols.
- [ ] Overlay detections for user review.
- [ ] Send only approved geometry to the application adapter.
- [ ] Preserve source-page and confidence provenance.

## Phase 12 - Revit and Basic 3D

Status: **Planned**

- [ ] Define a separate Revit adapter.
- [ ] Read active project, view, units, and levels.
- [ ] Create one native Revit element through the shared command platform.
- [ ] Define shared 3D profiles, heights, levels, and openings.
- [ ] Generate a small editable 3D building from approved 2D information.
- [ ] Keep Revit transactions and object identity application-specific.

## Phase 13 - AutoSPRINK and Fire-Protection Assistance

Status: **Planned**

- [ ] Research supported AutoSPRINK integration interfaces.
- [ ] Define domain objects for sprinklers, pipe, fittings, and connectivity.
- [ ] Prove one supported read-only operation.
- [ ] Prove one supported reversible write operation.
- [ ] Add deterministic, versioned engineering rules separately from AI reasoning.
- [ ] Require qualified human review for hazard classification, calculations, and compliance decisions.

## Phase 14 - Production Hardening

Status: **Planned**

- [ ] Local authentication and permissions.
- [ ] Installer and application-version checks.
- [ ] Structured logs and diagnostic exports.
- [ ] Crash, timeout, and reconnect recovery.
- [ ] Project-level audit history.
- [ ] Privacy controls and data-retention policy.
- [ ] Large-drawing and performance testing.
- [ ] Plugin compatibility matrix.
- [ ] User and developer documentation.

## Next Work While Waiting for the Plugin

The next backend task does not require changing teammate-owned code:

1. Complete command-result correlation in `backend/src/connection_manager.py`.
2. Update `backend/tests/test_api.py` for the live bridge behavior.
3. Add a test-only WebSocket client that returns a real correlated result over the transport.
4. Verify disconnected, timeout, malformed-result, and successful-result paths.
5. Document the final result envelope for the teammate.

After that work passes, the browser test client can be replaced by the real AutoCAD plugin without redesigning the Python side.

## Explicitly Deferred

Until the first live line is created and returned successfully, do not prioritize:

- autonomous full-drawing generation;
- hydraulic calculations;
- fire-code compliance claims;
- full PDF plan recognition;
- production databases;
- multi-user deployment;
- Revit or AutoSPRINK implementation;
- broad destructive editing tools.
