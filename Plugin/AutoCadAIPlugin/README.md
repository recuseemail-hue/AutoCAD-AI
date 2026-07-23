# AutoCAD AI Plugin

This .NET plugin executes validated `create_line` requests and bounded
read-only drawing queries on AutoCAD's UI thread. It returns traceable JSON
with document identity, object handles, drawing context, geometry properties,
and AutoCAD-AI provenance.

The checked-in Autodesk packages are version `26.0.0`, which is the **AutoCAD 2027 .NET API** and targets **.NET 10**. Use the matching AutoCAD release when loading this DLL. A different AutoCAD release requires matching Autodesk API package versions and target framework.

## Build

From PowerShell in this directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The execution-policy flag applies only to this build process and does not change the machine's PowerShell policy.

The loadable proof-of-concept assembly is written to:

```text
dist\AutoCadAIPlugin.dll
```

The normal MSBuild output is also available under `bin\Release\net10.0`. Autodesk runtime assemblies are intentionally not copied; AutoCAD supplies them when it loads the plugin.

## Load it in AutoCAD

1. Start AutoCAD 2027 and open or create a drawing.
2. Run `NETLOAD` at the AutoCAD command line.
3. Select `dist\AutoCadAIPlugin.dll`.
4. Run `AI_SERVER_STATUS`. It should report `http://localhost:8765/command`.

If AutoCAD blocks the file, add the project/output directory to AutoCAD's trusted locations or use PowerShell's `Unblock-File` on the DLL before loading it.

The plugin starts the local HTTP listener when it is loaded. The available AutoCAD commands are:

- `AI_SERVER_STATUS` — show listener status.
- `AI_SERVER_START` — start the listener on port 8765.
- `AI_SERVER_STOP` — stop the listener.
- `AI_DRAW_JSON` — paste a compact, single-line request directly into AutoCAD without HTTP.

If listener startup reports "Access is denied", reserve the local URL once from an elevated PowerShell window, then run `AI_SERVER_START` again:

```powershell
netsh http add urlacl url=http://localhost:8765/ user="$env:USERDOMAIN\$env:USERNAME"
```

## Send the request

Keep AutoCAD open and idle, then run this from the project directory:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8765/command" `
  -ContentType "application/json" `
  -InFile ".\examples\create-line.json"
```

Health check:

```powershell
Invoke-RestMethod -Uri "http://localhost:8765/health"
```

The server only binds to the local machine. It has no authentication and is intended as a proof of concept, not a network-facing production service.

## Unit conversion

Request coordinates are converted from `units` into the active drawing's `INSUNITS`. Supported request units are inches, feet, millimeters, centimeters, and meters. If the drawing is Unitless, the plugin assumes inches and returns a warning.

For the included 20-foot example, set `INSUNITS` to Inches (`1`) to receive an end coordinate of `[240, 0, 0]`, matching the example response. The line is created in world coordinates on layer `AI-WALL`; that layer is created when absent.

The returned `undo_token` is currently a correlation identifier (`cmd-001` becomes `ai-action-001`). Undo the most recent creation with AutoCAD's normal `UNDO` command; token-addressable undo is outside this proof of concept.

## HTTP behavior

- `POST /command` accepts up to 1 MB of JSON.
- `GET /health` reports listener health.
- Requests execute only after AutoCAD becomes idle, preventing database access from the HTTP background thread.
- A request times out after 30 seconds if AutoCAD remains busy and is then skipped rather than executed late.
- `requires_approval: true` is rejected without making a drawing change.

## Read-only schema v0.3 operations

- `get_drawing_context`
- `get_active_document`
- `get_drawing_units`
- `get_current_coordinate_system`
- `get_drawing_extents`
- `list_layers`
- `get_selected_entities`
- `get_entities_in_window`
- `get_entity_properties`
- `find_entities_by_import_id`

Read queries use read-mode transactions and never return an undo token.
Layer/entity collections are limited to at most 500 records. Window queries
use world coordinates and geometric-extents intersection.
