# AutoCAD-AI Architecture

## 1. Project Vision

AutoCAD-AI is a long-term project to create an AI-assisted design platform that lets a user communicate with CAD, BIM, and specialized design software through a conversational interface.

For the first version, **Odysseus will serve as the AI chat interface**. The user will describe what they want to create, inspect, modify, or automate. The AI will interpret the request, convert it into a structured and reviewable command, and send that command to an AutoCAD plugin. The plugin will then perform the actual drawing operation inside AutoCAD and return a result to the chat.

The first target application is AutoCAD. The system should be designed so that additional adapters can later support:

- Revit
- AutoSPRINK
- Civil 3D
- Inventor
- Blender or other 3D tools
- Other CAD, BIM, fabrication, and engineering applications

The long-term goal is not merely to make an AI that can draw lines. The goal is to create a controlled design assistant that can understand project context, propose actions, create or modify model elements, explain what it did, verify the result, and keep the user in control.

---

## 2. Core Goal for the First Working Version

The first complete proof of concept should allow this workflow:

```text
User types a request in Odysseus
              ↓
AI interprets the request
              ↓
AI creates a structured command
              ↓
Local bridge sends the command to AutoCAD
              ↓
AutoCAD plugin validates and executes it
              ↓
Plugin returns a success result or error
              ↓
Odysseus explains the result to the user
```

Example:

```text
User:
Create a 20-foot horizontal line on the AI-WALL layer.

AI proposal:
Create one line from (0, 0, 0) to (20, 0, 0) using feet as the
requested unit. Create the AI-WALL layer if it does not exist.

AutoCAD plugin result:
Line created successfully. Entity handle: 2A7. Layer: AI-WALL.
```

This simple end-to-end test is more important than beginning with complex plan generation. It proves that the entire communication chain works.

---

## 3. Intended User Experience

The desired interaction pattern is:

```text
Request → Interpret → Clarify → Preview → Approve → Execute → Verify
```

Not every command needs every step. A harmless command such as reading the active drawing units may execute immediately. A destructive or high-impact command should require approval.

A future interaction could look like this:

```text
User:
Lay out a 30-foot by 40-foot room with 6-inch walls, one centered
3-foot door on the south wall, and two equal windows on the east wall.

AI:
I will create the room on the A-WALL layer, place the door opening
at the center of the south wall, and place two 4-foot windows equally
spaced on the east wall. The room will be created at your current UCS
origin. Proceed?

User:
Yes.

System:
Created 4 wall assemblies, 1 door opening, 2 window openings, and
6 dimensions. No geometric conflicts were detected.
```

The system should be conversational, but its output must remain measurable, editable, and traceable.

---

## 4. Architectural Principles

### 4.1 AI interprets; deterministic software executes

The AI should determine intent and prepare a plan. It should not directly edit application memory or silently invent engineering geometry.

Deterministic code should handle:

- Coordinate calculations
- Units and conversions
- Object creation
- Geometric constraints
- Snapping and tolerances
- Intersections
- Layers and properties
- Selection filters
- File access
- Transactions
- Undo and rollback
- Engineering calculations
- Rules and standards checks

### 4.2 The AI must use structured commands

Natural language should never be the final instruction sent to a plugin. The AI should convert requests into a defined command format that can be validated before execution.

Example:

```json
{
  "schema_version": "0.1",
  "command_id": "cmd-001",
  "application": "autocad",
  "operation": "create_line",
  "parameters": {
    "start": [0.0, 0.0, 0.0],
    "end": [240.0, 0.0, 0.0],
    "layer": "AI-WALL"
  },
  "units": "inches",
  "requires_approval": false
}
```

### 4.3 Human control is required

The user should remain responsible for final design decisions. The system should request approval for ambiguous, destructive, expensive, or safety-critical actions.

Examples:

- Deleting objects
- Changing drawing units
- Moving a large selection
- Replacing blocks throughout a project
- Editing a central Revit model
- Changing pipe sizes
- Applying engineering or code assumptions
- Generating a complete model from incomplete information

### 4.4 Read before write

Whenever practical, the system should inspect the current application state before modifying it.

For example, before creating a line, it may check:

- Which drawing is active
- Whether the drawing is read-only
- Current units
- Current UCS
- Whether the requested layer exists
- Whether a transaction can be opened

### 4.5 Every action should be traceable

The system should record:

- Original user request
- AI interpretation
- Clarifications and assumptions
- Structured command
- Application target
- Objects created, changed, or deleted
- Warnings and validation results
- User approval
- Execution time
- Success or failure
- Undo or rollback information

### 4.6 Application-specific logic should remain separate

AutoCAD, Revit, and AutoSPRINK should be separate adapters rather than one large plugin.

```text
Shared AI and command layer
├── AutoCAD adapter
├── Revit adapter
├── AutoSPRINK adapter
└── Future adapters
```

The shared layer should describe intent. Each adapter should translate that intent into application-specific API calls.

### 4.7 Build small reliable tools before autonomous workflows

Complex actions should be composed from small tested operations. The first commands should create simple entities and read drawing information. More advanced features should be added only after those operations are reliable.

---

## 5. Proposed System Components

## 5.1 Odysseus Chat Interface

Odysseus is the initial user-facing interface.

Responsibilities:

- Accept natural-language requests
- Display project and application status
- Ask clarification questions
- Show proposed operations
- Request approval
- Display warnings and errors
- Present execution results
- Maintain conversation history
- Allow the user to revise a request

Odysseus should not contain all geometry or application logic. It should coordinate other services.

---

## 5.2 AI Reasoning and Orchestration Layer

This layer turns a request into a safe, structured plan.

Responsibilities:

- Identify user intent
- Determine the target application
- Determine whether more information is needed
- Break a complex request into smaller operations
- Select the correct tools
- Produce structured commands
- Interpret plugin responses
- Explain errors and warnings
- Suggest corrections
- Maintain short-term project context

The AI model should be replaceable. The architecture should not depend on one model provider forever.

---

## 5.3 Shared Command Schema

The command schema is the contract between the AI layer, backend, and plugins.

It should be:

- Explicit
- Versioned
- Machine-validatable
- Independent of a particular AI model
- Mostly independent of a particular design application
- Easy to log and test
- Safe to reject when incomplete

Possible command families follow.

### Read commands

- Get active document
- Get drawing or model units
- Get current UCS or project coordinates
- Get layers, levels, views, and worksets
- Get selected objects
- Get object properties
- Get drawing extents
- Get block or family definitions
- Get model statistics
- Get connected pipe information

### Create commands

- Create line
- Create polyline
- Create arc
- Create circle
- Create text
- Create dimension
- Create layer
- Insert block
- Create wall
- Place family
- Create pipe
- Place sprinkler

### Modify commands

- Move
- Copy
- Rotate
- Scale
- Offset
- Trim
- Extend
- Join
- Change layer or type
- Change object properties
- Change elevation
- Change size

### Delete and rollback commands

- Delete selected objects
- Delete by stable object identifier
- Delete all objects created by a command group
- Undo the last AI action
- Restore a saved checkpoint

### Higher-level commands

- Create a room layout
- Trace a floor plan
- Place a repeated grid of objects
- Build a wall assembly
- Route a pipe between points
- Create a riser diagram
- Lay out sprinkler branch lines
- Generate a basic 3D model

Higher-level commands should be decomposed into tested lower-level operations.

---

## 5.4 Local Backend or Bridge

A local service will connect Odysseus to the application plugins running on the user's computer.

Possible responsibilities:

- Receive structured requests
- Validate command schemas
- Authenticate local clients
- Track which applications are connected
- Route commands to the correct adapter
- Queue operations
- Manage timeouts
- Return results
- Store logs
- Manage project context
- Prevent unauthorized commands
- Translate between shared and application-specific schemas

Possible communication methods:

- Local HTTP API
- WebSocket connection
- Named pipes
- MCP-compatible tool server

A practical first choice is a local HTTP or WebSocket service because it is easy to inspect and test. MCP can be added as an interface layer if it fits the Odysseus integration.

---

## 5.5 AutoCAD Plugin

The AutoCAD plugin will likely be written in C# using the AutoCAD .NET API.

Responsibilities:

- Connect to the local bridge
- Report connection and document status
- Read the active drawing safely
- Validate incoming AutoCAD commands
- Execute changes inside AutoCAD transactions
- Return stable identifiers for affected entities
- Return warnings and errors
- Group related actions for undo
- Reject unsupported commands
- Avoid modifying the drawing when validation fails

Initial plugin commands should be deliberately small:

1. Ping the plugin
2. Get active drawing name
3. Get drawing units
4. Get current layer
5. List layers
6. Create a layer
7. Create a line
8. Create a polyline
9. Create a circle
10. Create text
11. Select an entity by handle or object ID
12. Move a selected entity
13. Delete an entity with confirmation
14. Undo the most recent AI command group

---

## 5.6 Application Adapters

Each supported program should have an adapter that translates shared commands into the application's own concepts.

### AutoCAD adapter

Typical concepts:

- Drawing database
- Model space and paper space
- Layers
- Blocks
- Entities
- Handles and object IDs
- UCS and WCS
- Transactions

### Revit adapter

Typical concepts:

- Documents
- Views
- Levels
- Grids
- Families and types
- Elements and element IDs
- Worksets
- Parameters
- Transactions
- Central and local models

### AutoSPRINK adapter

Typical concepts may include:

- Sprinklers
- Pipes
- Fittings
- Elevations
- Nodes
- Hydraulic calculation data
- Remote areas
- System components

The actual AutoSPRINK integration path needs research. It may require a supported API, automation interface, file exchange, or controlled interaction through AutoCAD-compatible features.

---

## 5.7 Geometry and Modeling Engine

A shared geometry engine may eventually support operations that should work consistently across applications.

Possible capabilities:

- Vectors and coordinate transforms
- Unit conversion
- Line, arc, and polyline calculations
- Intersections
- Offsets
- Snapping
- Collinearity checks
- Closed-loop detection
- Polygon operations
- Constraint solving
- 2D-to-3D extrusion
- Collision detection
- Spatial indexing

This engine should calculate intended geometry before an application adapter creates native objects.

---

## 5.8 Rules and Validation Engine

A separate validation layer may eventually evaluate commands before and after execution.

Possible checks:

- Required parameters are present
- Units are explicit
- Coordinates are within a reasonable range
- Referenced objects still exist
- Geometry is not degenerate
- Objects do not unintentionally overlap
- Requested layer, type, family, or pipe size is valid
- Application state allows modification
- A command is allowed by the current safety policy
- Design rules or standards are satisfied

For fire protection work, code-related assistance must be transparent, edition-specific, and reviewable. The system should never present AI output as a substitute for professional judgment or approved calculations.

---

## 5.9 Project Context and Memory

The system may eventually maintain a project context package containing:

- Project name and identifier
- Target application
- Units
- Coordinate conventions
- Layer standards
- Family and block libraries
- Drawing references
- User preferences
- Design assumptions
- Approved command history
- Ruleset and code edition
- Discipline-specific data

The AI should retrieve only the context needed for the current request rather than loading an entire project into every prompt.

---

## 5.10 Logging, Testing, and Diagnostics

The platform should make failures understandable.

Logs should distinguish between:

- User request errors
- AI interpretation errors
- Schema validation errors
- Connection errors
- Plugin errors
- Application API errors
- Geometry validation errors
- Unsupported operations

Testing should include:

- Unit tests for command validation
- Unit tests for geometry functions
- Mock plugin tests
- Integration tests with AutoCAD
- Saved command fixtures
- Regression drawings
- Failure and rollback tests

---

## 6. Safety and Permission Model

Commands can be grouped by risk.

### Low-risk, normally automatic

- Read drawing information
- List layers
- Count selected objects
- Highlight objects
- Create a preview

### Medium-risk, approval depending on scope

- Create geometry
- Move or copy selected objects
- Change properties
- Insert blocks or families
- Create dimensions

### High-risk, approval required

- Delete objects
- Modify many objects
- Change project units or coordinates
- Overwrite files
- Edit a shared or central model
- Change engineering sizes or system types
- Run automated code-driven design changes

The user should be able to configure stricter approval rules.

---

## 7. 2D and 3D Capability Path

The system can grow through several levels.

### Level 1: 2D primitives

- Lines
- Polylines
- Arcs
- Circles
- Text
- Dimensions
- Layers

### Level 2: 2D design objects

- Walls represented as linework
- Doors and windows represented as blocks
- Rooms
- Equipment layouts
- Pipe routes
- Sprinkler symbols

### Level 3: Native BIM and domain objects

- Revit walls, doors, rooms, and families
- Revit MEP systems
- AutoSPRINK pipes, fittings, and sprinklers
- Parameter-driven components

### Level 4: 3D generation

- Extrude closed profiles
- Generate walls from floor plans
- Place floors and roofs
- Add openings
- Place equipment and components
- Build simple complete structures

### Level 5: Multi-application coordination

- Read an AutoCAD background and create a Revit model
- Transfer approved geometry between applications
- Compare CAD, BIM, and sprinkler layouts
- Keep common project references synchronized
- Generate application-specific deliverables from one intent model

---

## 8. Possible Long-Term Capabilities

The architecture could eventually support:

### Conversational drafting

- “Draw this wall 12 feet long.”
- “Offset these lines 6 inches.”
- “Place a door in the center of this wall.”
- “Move every sprinkler in this bay 6 inches east.”

### Drawing understanding

- Summarize a plan
- Identify rooms and boundaries
- Find repeated symbols
- Recognize dimensions and notes
- Identify missing labels
- Compare revisions

### Automated repetitive work

- Layer cleanup
- Renaming
- Block replacement
- Sheet setup
- View creation
- Dimension placement
- Repeated object placement
- Parameter updates

### QA and model review

- Detect disconnected geometry
- Find duplicate objects
- Identify impossible dimensions
- Find coordination conflicts
- Flag inconsistent types or layers
- Explain likely modeling errors

### Image and PDF to model

- Trace clean plan images
- Extract vector geometry from PDFs
- Recognize walls, doors, windows, and symbols
- Convert approved results into CAD or BIM objects
- Use dimensions to establish scale

### 3D model generation

- Generate basic buildings from plans and instructions
- Add levels, walls, floors, roofs, and openings
- Place parametric objects
- Export to supported modeling tools

### Fire sprinkler assistance

- Recognize sprinkler and pipe symbols
- Place sprinklers using an approved layout strategy
- Route branch lines and mains
- Build riser diagrams
- Find disconnected piping
- Read hydraulic and system data
- Assist with design checks
- Generate review reports

Engineering and code decisions must use deterministic, versioned rules and must remain subject to qualified human review.

---

## 9. Initial Repository Direction

A possible early structure is:

```text
AutoCAD-AI/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   ├── commands/
│   │   ├── orchestration/
│   │   ├── validation/
│   │   └── main.py
│   └── tests/
├── plugins/
│   └── autocad/
├── schemas/
├── docs/
│   ├── architecture.md
│   └── roadmap.md
├── examples/
├── README.md
├── requirements.txt
└── .gitignore
```

This is a direction, not a requirement for immediate implementation. Folders should be created when they have a real purpose.

---

## 10. Important Open Decisions

The following decisions should be worked through before heavy implementation:

1. How will Odysseus call local tools?
2. Will the first bridge use HTTP, WebSockets, MCP, or a combination?
3. Which AutoCAD version will be the initial target?
4. Which .NET version is required by that AutoCAD version?
5. Will AutoCAD initiate the connection, or will the bridge connect to AutoCAD?
6. How will commands be authenticated locally?
7. What is the first command schema version?
8. How will entity identifiers remain useful after save, reopen, copy, or undo?
9. Which actions require approval by default?
10. How will the system preview operations before execution?
11. How will undo and rollback be grouped?
12. How will project context be stored?
13. How will logs avoid exposing confidential project data?
14. What supported integration options actually exist for AutoSPRINK?
15. When should a capability be shared versus application-specific?

---

## 11. Current Scope and Non-Goals

### Current scope

- Define the system clearly
- Establish a safe command architecture
- Use Odysseus as the first chat interface
- Build one reliable AutoCAD connection
- Support a small set of read and create operations
- Return useful results and errors

### Not an immediate goal

- Fully autonomous building design
- Automatic code compliance approval
- Complete image-to-BIM conversion
- Supporting every AutoCAD command
- Supporting AutoCAD, Revit, and AutoSPRINK simultaneously
- Generating production-ready engineering drawings without review
- Directly writing complex DWG files without AutoCAD

---

## 12. First Architectural Milestone

The first milestone is complete when all of the following work:

1. Odysseus can invoke a local AutoCAD tool.
2. The tool can determine whether AutoCAD and the plugin are connected.
3. Odysseus can request the active drawing name and units.
4. Odysseus can send a validated `create_line` command.
5. The plugin creates the line in one AutoCAD transaction.
6. The plugin returns the entity identifier and result.
7. The result is displayed in Odysseus.
8. The entire action can be undone as one operation.
9. Errors are returned without leaving a partial drawing change.

That end-to-end connection should be proven before adding advanced AI interpretation, image recognition, Revit, AutoSPRINK, or 3D generation.