# AutoCAD-AI

AutoCAD-AI is a long-term project to create an AI-assisted design platform that allows users to control CAD, BIM, and specialized design applications through a conversational interface.

The first version will use **Odysseus as the AI chat interface** and **AutoCAD as the first target application**. A user will describe what they want to create, inspect, modify, or automate. The AI will interpret the request, convert it into a structured command, and send it through a local bridge to an AutoCAD plugin. The plugin will validate and execute the operation inside AutoCAD, then return the result to the chat.

The project is intended to later expand into:

- Revit
- AutoSPRINK
- Civil 3D
- Inventor
- Blender and other 3D tools
- Additional CAD, BIM, fabrication, and engineering applications

## Project Mission

Build a controlled AI design assistant that can:

- Understand natural-language design requests
- Inspect the active drawing or model
- Ask for missing information
- Propose measurable and reviewable actions
- Create and modify native application objects
- Explain what it plans to do
- Request approval when appropriate
- Validate the result
- Return clear success messages, warnings, and errors
- Preserve an auditable history of its actions
- Keep the user responsible for final design decisions

The goal is not merely to make an AI that can draw lines. The goal is to create a reliable platform that connects conversational AI to professional design software while keeping geometry, calculations, safety rules, and application execution deterministic and reviewable.

## Initial System Architecture

```text
User
  ↓
Odysseus chat interface
  ↓
AI reasoning and command planning
  ↓
Structured, versioned JSON command
  ↓
Local HTTP Bridge Pipeline (Port 8080)
  ↓
AutoCAD C# Plugin (.NET 10.0 Client Listener)
  ↓
AutoCAD drawing database (Safe Transaction Execution)
  ↓
Execution result returned to Odysseus
```

The desired interaction pattern is:

```text
Request → Interpret → Clarify → Preview → Approve → Execute → Verify
```

Not every action will require every step. Reading the current drawing units may happen immediately, while destructive, ambiguous, or safety-critical changes should require explicit approval.

## First Proof of Concept

The first complete milestone will prove the entire communication path with a very small feature set.

A user should be able to ask Odysseus to:

1. Connect to the active AutoCAD session.
2. Read the active drawing name and units.
3. Create one line using explicit coordinates, units, and layer information.
4. Return the result to Odysseus.
5. Undo the AI-created operation as one command group.

Example:

```text
User:
Create a 20-foot horizontal line on the AI-WALL layer.

AI proposal:
Create one line from (0, 0, 0) to (20, 0, 0), using feet as the
requested unit. Create the AI-WALL layer if it does not exist.

AutoCAD result:
Line created successfully on AI-WALL.
```

This simple workflow is the immediate target. More advanced automation should wait until this end-to-end path is reliable.

## Core Design Principles

### AI interprets; deterministic software executes

The AI will determine intent, ask questions, and prepare a plan. Deterministic code will handle precise operations such as:

- Coordinates and transformations
- Units and conversions
- Entity creation
- Layers and object properties
- Geometric constraints
- Snapping and tolerances
- Selection and transactions
- Undo and rollback
- Engineering calculations
- Rules and standards checks

### Structured commands instead of raw natural language

The application plugin should never receive an unrestricted natural-language instruction as its final command. The AI should produce a defined structure that can be validated before execution.

Example Request Package (`POST http://localhost:8080/command/`):
```json
{
  "schema_version": "0.1",
  "command_id": "cmd-001",
  "application": "autocad",
  "operation": "create_line",
  "parameters": {
    "start": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "end": { "x": 20.0, "y": 0.0, "z": 0.0 },
    "layer": "AI-WALL",
    "create_layer_if_missing": true
  },
  "units": "feet",
  "coordinate_system": "world",
  "requires_approval": false
}
```

### Read before write

Before changing a drawing or model, the system should inspect relevant application state whenever practical, including:

- Active document
- Read-only status
- Drawing or project units
- Coordinate system
- Current layer
- Existing layers and blocks
- Current selection
- Application connection status

### Human control

The user should remain in control. Approval should be required for operations such as:

- Deleting objects
- Changing units
- Replacing objects throughout a project
- Moving large selections
- Editing a shared or central model
- Changing pipe sizes
- Applying engineering assumptions
- Generating major portions of a model from incomplete information

### Traceable and recoverable actions

The system should record:

- Original user request
- AI interpretation
- Assumptions and clarifications
- Structured command
- Target application and document
- Objects created, modified, or deleted
- Warnings and validation results
- Approval status
- Success or failure
- Undo or rollback information

## Planned Capabilities

### AutoCAD

- Read drawing and selection information
- Create lines, polylines, arcs, circles, text, dimensions, and blocks
- Create and manage layers
- Move, copy, rotate, scale, offset, trim, extend, and join objects
- Perform repetitive drafting and cleanup tasks
- Create higher-level objects from smaller validated commands
- Use images and PDFs as references
- Generate or revise 2D drawing geometry

### Revit

- Read project, view, level, family, and element information
- Create native walls, floors, roofs, rooms, doors, windows, and families
- Place and modify model elements using levels and constraints
- Create views, sheets, tags, and schedules
- Assist with BIM coordination and model review

### AutoSPRINK

- Inspect sprinkler, pipe, fitting, elevation, and system information
- Create or modify native sprinkler-system objects where supported
- Assist with repetitive layout and drafting work
- Support pipe routing and system modeling
- Use deterministic checks for geometry, calculations, and applicable rules
- Preserve mandatory human review for fire-protection design decisions

### Images, PDFs, and Existing Drawings

- Read raster and vector plan references
- Identify lines, walls, rooms, dimensions, symbols, and text
- Suggest scale and coordinate alignment
- Convert approved interpretations into native drawing or model objects
- Compare references with the current drawing
- Detect omissions or inconsistencies for user review

### 3D Modeling

- Generate basic 3D geometry from written instructions
- Build 3D models from 2D plans and elevations
- Identify walls, openings, levels, and heights
- Create native Revit elements or general-purpose meshes
- Coordinate 2D and 3D representations
- Export to supported modeling and visualization tools

## Application Adapter & IPC Strategy

Application-specific logic is strictly decoupled using isolated target adapters. Communication between the Python AI layer and the active design software session runs locally through a dedicated Inter-Process Communication (IPC) boundary.

```text
Shared AI and command layer
        │
  (Local HTTP/JSON)
        ▼
├── AutoCAD Adapter (C# Plugin Listener - Port 8080)
├── Revit Adapter
├── AutoSPRINK Adapter
└── Future application adapters
```

### C# AutoCAD Plugin Specifications
*   **Target Engine Environment**: `.NET 10.0-windows` (Modern SDK-Style Architecture)
*   **Host System Compatibility**: AutoCAD 2027 (`AutoCAD.NET` NuGet APIs >= v26.0.0)
*   **Embedded Communication Channel**: Native asynchronous `System.Net.HttpListener` initialized directly on plugin assembly load via `IExtensionApplication`.
*   **Default Endpoint Route**: `http://localhost:8080/command/`

## Current Project Phase

The project is transitioning from **planning** into **initial component assembly**.

Current priorities:
- Implement thread marshaling for incoming non-UI asynchronous HTTP requests inside AutoCAD.
- Build the core C# Database transaction engine loop for geometry generation.
- Configure mock Python client routing matrices to transmit valid payloads to `localhost:8080`.
- Standardize the `ExecutionResponse` JSON contract structure.

## Repository Layout Structure

```text
AutoCAD-AI/
├── backend/                  # Python reasoning & API management
│   ├── src/
│   └── tests/
└── plugins/                  # Target environment automation tools
    └── AutoCadAIPlugin/       # C# Plugin Application Solution
        ├── Commands/         # Manual AutoCAD Text CLI Wrappers
        │   └── Commands.cs
        ├── Models/           # Strongly-typed Serialization Contracts (POCOs)
        │   ├── RequestModels.cs
        │   └── ResponseModels.cs
        ├── Services/         # Deterministic Transaction Layer & IPC Bridge
        │   ├── DrawingService.cs
        │   └── PythonBridge.cs
        ├── Initialization.cs # Application Plugin Entry Lifecycle Control
        └── AutoCadAIPlugin.csproj
```
