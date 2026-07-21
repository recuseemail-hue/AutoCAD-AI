# AutoCAD-AI Roadmap

## 1. Project Mission

Create an AI-assisted design platform that begins with an Odysseus chat interface controlling a safe AutoCAD plugin and later expands into Revit, AutoSPRINK, and AI-assisted 3D model generation.

The platform should let a user describe a desired result in normal language while deterministic software performs the exact geometry, application, and engineering operations.

The immediate objective is not to build every feature. It is to design the system well, prove the full communication path with a very small AutoCAD feature set, and then expand without rebuilding the project from scratch.

---

## 2. Product Direction

### Near-term product

A conversational AutoCAD assistant that can:

- Connect to the active AutoCAD session
- Read basic drawing information
- Create simple drawing entities
- Modify selected entities
- Explain what it plans to do
- Ask for approval when appropriate
- Return clear results and errors
- Group AI actions into undoable operations

### Mid-term product

A drawing assistant that can:

- Understand larger drafting requests
- Work with layers, blocks, dimensions, and object properties
- Inspect drawings and selections
- Perform repetitive cleanup and layout work
- Use images and PDFs as reference information
- Recognize common plan objects
- Build compound objects from simple commands

### Long-term product

A multi-application design assistant that can:

- Work in AutoCAD, Revit, and AutoSPRINK
- Generate native 2D and 3D objects
- Coordinate information between applications
- Interpret plans and specifications
- Assist with discipline-specific workflows
- Use deterministic rules for geometry, calculations, and code checks
- Maintain project context and an auditable action history

---

## 3. Guiding Rules for Development

1. Prove one complete workflow before adding many features.
2. Keep natural-language reasoning separate from application execution.
3. Use structured, versioned commands between components.
4. Make reading application state reliable before allowing broad write access.
5. Keep every action undoable or recoverable where possible.
6. Require approval for destructive, ambiguous, or safety-critical actions.
7. Build application adapters separately.
8. Use deterministic geometry and rules instead of relying on AI guesses.
9. Log what the system intended, executed, and returned.
10. Add tests for every command before combining commands into complex workflows.

---

# Phase 0 — Planning and System Definition

## Goal

Agree on what the project is, how the major parts communicate, and what the first proof of concept must demonstrate.

## Questions to answer

- [ ] What exact role will Odysseus play?
- [ ] Which AI model will Odysseus use initially?
- [ ] Can Odysseus call local tools directly, through MCP, or through an HTTP service?
- [ ] Which AutoCAD version will be supported first?
- [ ] Which .NET runtime does that AutoCAD version require?
- [ ] Will the AutoCAD plugin connect outward to a bridge, or will the bridge call the plugin?
- [ ] What commands will exist in schema version 0.1?
- [ ] Which commands require user approval?
- [ ] How will command history and logs be stored?
- [ ] How will undo and rollback work?
- [ ] How will application and project context be represented?
- [ ] What information may leave the local computer?
- [ ] What is the first practical AutoSPRINK integration path?

## Documents to maintain

- [x] Project architecture
- [x] Project roadmap
- [ ] Command schema draft
- [ ] Safety and approval policy
- [ ] First proof-of-concept sequence diagram
- [ ] Application support matrix
- [ ] Decision log

## Completion criteria

The team can explain the first system in one sentence:

> A user asks Odysseus to perform a simple AutoCAD operation; Odysseus sends a validated structured command through a local bridge; an AutoCAD plugin executes the command and returns a result.

---

# Phase 1 — Repository and Development Foundation

## Goal

Create a clean project foundation that can support a Python backend and one or more application plugins.

## Tasks

- [x] Create GitHub repository
- [x] Install Python
- [x] Create Python virtual environment
- [x] Install initial Python packages
- [x] Create `requirements.txt`
- [x] Create initial folders
- [x] Create architecture documentation
- [x] Create roadmap documentation
- [ ] Add `.gitignore`
- [ ] Decide whether to keep or remove the early image-processing dependencies
- [ ] Create a minimal backend entry point
- [ ] Create a test folder and first automated test
- [ ] Add a configuration example file
- [ ] Add basic logging
- [ ] Define branch and commit conventions
- [ ] Make a clean foundation commit

## Possible repository structure

```text
AutoCAD-AI/
├── backend/
│   ├── src/
│   └── tests/
├── plugins/
│   └── autocad/
├── schemas/
├── docs/
├── examples/
├── README.md
├── requirements.txt
└── .gitignore
```

## Completion criteria

- The repository has no generated virtual-environment files tracked by Git.
- The backend runs a simple health-check command.
- The test suite can be run with one command.
- The architecture and roadmap match the current product direction.

---

# Phase 2 — Command Schema Prototype

## Goal

Define the structured language used by Odysseus, the backend, and the application plugins.

## Initial command envelope

Every request should include fields similar to:

- Schema version
- Command ID
- Target application
- Operation name
- Parameters
- Units
- Document target
- Preconditions
- Approval status
- Requested timeout
- Metadata for logging

## First proposed operations

### Connection and status

- [ ] `ping`
- [ ] `get_application_status`
- [ ] `get_active_document`

### Read operations

- [ ] `get_units`
- [ ] `get_current_layer`
- [ ] `list_layers`
- [ ] `get_selection`
- [ ] `get_entity_properties`

### Create operations

- [ ] `create_layer`
- [ ] `create_line`
- [ ] `create_polyline`
- [ ] `create_circle`
- [ ] `create_text`

### Modify operations

- [ ] `move_entities`
- [ ] `copy_entities`
- [ ] `change_layer`

### Safety operations

- [ ] `preview_command`
- [ ] `approve_command`
- [ ] `cancel_command`
- [ ] `undo_command_group`

## Tasks

- [ ] Write JSON Schema or equivalent validation models
- [ ] Add example valid commands
- [ ] Add example invalid commands
- [ ] Define consistent error responses
- [ ] Define result objects and affected-entity identifiers
- [ ] Add schema unit tests
- [ ] Version the schema as `0.1`

## Completion criteria

A backend test can accept a valid `create_line` request, reject an invalid one, and return a predictable result structure without needing AutoCAD.

---

# Phase 3 — Local Bridge Proof of Concept

## Goal

Create a local service that can receive commands and communicate with a simulated plugin.

## Tasks

- [ ] Choose HTTP, WebSocket, MCP, or a combined approach
- [ ] Create a health endpoint
- [ ] Create a command endpoint
- [ ] Add request validation
- [ ] Add command IDs and correlation IDs
- [ ] Add timeouts
- [ ] Add structured error responses
- [ ] Add local authentication or connection token
- [ ] Create a mock AutoCAD adapter
- [ ] Log requests and results
- [ ] Test reconnect behavior

## Completion criteria

A local test client sends a `create_line` command to the bridge, the mock adapter receives it, and the bridge returns a success response.

---

# Phase 4 — AutoCAD Plugin Connection

## Goal

Prove reliable two-way communication between the local bridge and an AutoCAD plugin.

## Tasks

- [ ] Confirm initial AutoCAD version
- [ ] Create the C# plugin project
- [ ] Reference the correct AutoCAD .NET assemblies
- [ ] Create a basic command that proves the plugin loaded
- [ ] Load the plugin with `NETLOAD`
- [ ] Add a plugin status panel or command
- [ ] Connect the plugin to the local bridge
- [ ] Implement `ping`
- [ ] Implement `get_active_document`
- [ ] Implement `get_units`
- [ ] Handle AutoCAD document locking and transactions correctly
- [ ] Return clear connection errors

## Completion criteria

Odysseus or a temporary test client can ask for the active drawing name and units and receive the correct response from AutoCAD.

---

# Phase 5 — First AutoCAD Drawing Operations

## Goal

Create a small, dependable set of drawing tools.

## Tasks

- [ ] Create a layer
- [ ] Create a line
- [ ] Create a polyline
- [ ] Create a circle
- [ ] Create text
- [ ] Return handles or stable identifiers
- [ ] Group each AI request into one undoable action
- [ ] Validate units and coordinates
- [ ] Reject invalid or degenerate geometry
- [ ] Return affected entity properties
- [ ] Add integration tests using a clean test drawing

## Completion criteria

A user can ask Odysseus to create a line with a defined length, location, and layer. The line appears correctly in AutoCAD, the result is returned to Odysseus, and the action can be undone in one step.

---

# Phase 6 — Odysseus End-to-End Integration

## Goal

Use Odysseus as the real conversational interface rather than a temporary test client.

## Tasks

- [ ] Expose the bridge as tools Odysseus can call
- [ ] Define the system prompt and tool instructions
- [ ] Require structured tool arguments
- [ ] Add clarification behavior for missing dimensions or units
- [ ] Show planned operations before high-risk actions
- [ ] Display plugin warnings clearly
- [ ] Return concise execution summaries
- [ ] Keep an action history in the conversation
- [ ] Test incorrect and ambiguous user requests

## Example tests

- [ ] “Draw a 10-foot line.” The system asks where or applies an explicitly documented default.
- [ ] “Delete that.” The system identifies the target and requests confirmation.
- [ ] “Make a 20-by-30 room.” The system proposes geometry and asks required questions.
- [ ] “Put it on the wall layer.” The system resolves or creates the intended layer safely.

## Completion criteria

A user can complete the full request-to-result workflow entirely through Odysseus.

---

# Phase 7 — Read, Select, and Modify Existing Geometry

## Goal

Allow the assistant to understand and change existing drawing objects, not only create new ones.

## Tasks

- [ ] Read current selection
- [ ] Query entities by layer, type, handle, or region
- [ ] Return object properties
- [ ] Highlight proposed targets
- [ ] Move entities
- [ ] Copy entities
- [ ] Rotate entities
- [ ] Change layers and properties
- [ ] Offset entities
- [ ] Delete entities with approval
- [ ] Detect stale object references
- [ ] Add rollback tests

## Completion criteria

The user can select objects in AutoCAD, describe a modification in Odysseus, preview the intended targets, approve it, and receive a verified result.

---

# Phase 8 — Compound Drafting Workflows

## Goal

Combine primitive commands into useful drafting operations.

## Possible workflows

- [ ] Create a rectangular room
- [ ] Create wall thickness using offsets
- [ ] Place a centered door opening
- [ ] Place repeated windows
- [ ] Generate a column grid
- [ ] Place repeated blocks at spacing
- [ ] Add dimensions
- [ ] Create and populate layers
- [ ] Clean duplicate or short geometry
- [ ] Align and distribute objects

## Development rule

Every compound workflow must be decomposable into logged primitive operations and must support preview and rollback.

## Completion criteria

A multi-step request creates a predictable group of editable AutoCAD objects and can be undone as one command group.

---

# Phase 9 — Drawing and Project Awareness

## Goal

Give the assistant enough context to work intelligently within a real project.

## Tasks

- [ ] Read drawing extents
- [ ] Read block definitions
- [ ] Read named views and layouts
- [ ] Read layers and standards
- [ ] Store project units and coordinate conventions
- [ ] Store approved assumptions
- [ ] Reference external drawings safely
- [ ] Summarize the current drawing
- [ ] Detect unsupported or missing context
- [ ] Add a project context file or database

## Completion criteria

The assistant can answer basic questions about the active drawing and use project standards in later commands without repeatedly asking for the same information.

---

# Phase 10 — Image and PDF Understanding

## Goal

Use images and PDFs as source information for drafting and modeling.

## Possible capabilities

- [ ] Upload a floor-plan image or PDF through Odysseus
- [ ] Detect whether a PDF contains vector data
- [ ] Extract vector lines when available
- [ ] Rasterize scanned pages when needed
- [ ] Detect straight lines, arcs, and text
- [ ] Recognize dimensions
- [ ] Determine scale from a known reference
- [ ] Create a visual preview
- [ ] Let the user accept or reject detected geometry
- [ ] Send approved geometry to AutoCAD

## Completion criteria

A clean source plan can be traced into editable AutoCAD geometry with an approval step and known scale.

---

# Phase 11 — Domain Object Recognition

## Goal

Recognize that drawing elements represent real design objects rather than only generic lines.

## Possible objects

- Walls
- Doors
- Windows
- Rooms
- Columns
- Equipment
- Plumbing fixtures
- Electrical symbols
- Sprinklers
- Valves
- Pipes
- Fittings

## Tasks

- [ ] Define object schemas
- [ ] Build labeled examples
- [ ] Evaluate rule-based recognition
- [ ] Evaluate template matching
- [ ] Evaluate vision models where useful
- [ ] Require user review for uncertain classifications
- [ ] Convert approved detections into native CAD objects or blocks

## Completion criteria

The assistant can identify at least one object class reliably and create or place the corresponding editable object.

---

# Phase 12 — Revit Adapter

## Goal

Extend the shared platform into Revit while creating native Revit elements.

## Initial Revit operations

- [ ] Connect to Revit
- [ ] Get active document and view
- [ ] List levels
- [ ] List family types
- [ ] Create a level
- [ ] Create a wall
- [ ] Place a family instance
- [ ] Create a floor
- [ ] Read and set parameters
- [ ] Group changes into transactions
- [ ] Handle central and local model safety

## Completion criteria

A user can ask Odysseus to create a small native Revit element using the same general command architecture used for AutoCAD.

---

# Phase 13 — Basic 3D Model Generation

## Goal

Generate simple native or exportable 3D models from structured instructions and approved 2D information.

## Tasks

- [ ] Define a shared 3D geometry representation
- [ ] Create closed profiles
- [ ] Extrude profiles
- [ ] Generate walls at assigned heights
- [ ] Create floors and roofs
- [ ] Add doors and windows
- [ ] Place repeated components
- [ ] Validate intersections and openings
- [ ] Create an interactive preview
- [ ] Export or create native application geometry

## Possible first project

Generate a small rectangular single-story building from:

- Exterior dimensions
- Wall thickness
- Wall height
- Door and window locations
- Roof type

## Completion criteria

The system creates a simple, dimensionally correct 3D building that remains editable in the target application.

---

# Phase 14 — AutoSPRINK Adapter

## Goal

Add specialized fire sprinkler design capabilities through a supported and reliable AutoSPRINK integration method.

## Research tasks

- [ ] Identify official AutoSPRINK APIs or automation interfaces
- [ ] Determine whether a plugin can be loaded directly
- [ ] Investigate AutoCAD-compatible interfaces
- [ ] Investigate supported import and export formats
- [ ] Determine how objects, nodes, and connectivity are represented
- [ ] Determine how hydraulic information can be read safely
- [ ] Establish licensing and redistribution limitations

## Possible future operations

- [ ] Read selected sprinkler properties
- [ ] Place a sprinkler
- [ ] Draw connected pipe
- [ ] Insert fittings
- [ ] Change pipe size or elevation
- [ ] Find disconnected system components
- [ ] Build branch-line layouts
- [ ] Create riser components
- [ ] Identify remote areas
- [ ] Read calculation results
- [ ] Generate review reports

## Safety requirement

Hydraulic calculations, code compliance, and engineering decisions must be handled through deterministic, reviewable logic and qualified human approval. The AI should assist rather than act as the final authority.

## Completion criteria

One supported AutoSPRINK operation can be requested through Odysseus, executed safely, and verified in the application.

---

# Phase 15 — Rules, Standards, and Engineering Assistance

## Goal

Add reviewable, versioned rules that can assist discipline-specific design without hiding assumptions.

## Tasks

- [ ] Create a ruleset format
- [ ] Store standard and edition metadata
- [ ] Cite the rule used in each result
- [ ] Separate mandatory rules from preferences
- [ ] Record project-specific overrides
- [ ] Build deterministic calculations
- [ ] Add test cases for each rule
- [ ] Require review for uncertain interpretations
- [ ] Generate a clear validation report

## Completion criteria

The system can evaluate a narrow, well-defined rule and explain the inputs, rule version, result, and any assumptions.

---

# Phase 16 — Multi-Application Coordination

## Goal

Use one conversational workflow to coordinate data and approved operations across several applications.

## Possible workflows

- [ ] Read an AutoCAD floor plan and create a Revit model
- [ ] Compare AutoCAD and Revit geometry
- [ ] Import approved Revit background information into a sprinkler workflow
- [ ] Check sprinkler locations against architectural elements
- [ ] Translate a shared intent model into multiple application deliverables
- [ ] Keep references and coordinates synchronized

## Completion criteria

A small approved geometry set can be transferred between two applications without losing units, coordinates, identity, or intent.

---

# Phase 17 — Production Hardening

## Goal

Make the platform dependable enough for repeated real-project use.

## Tasks

- [ ] Installer and update process
- [ ] Version compatibility checks
- [ ] Secure local authentication
- [ ] Permission settings
- [ ] Crash recovery
- [ ] Command queue recovery
- [ ] Detailed diagnostic logs
- [ ] Privacy controls
- [ ] Project backup and restore
- [ ] Performance testing
- [ ] Large-drawing testing
- [ ] Plugin compatibility matrix
- [ ] User documentation
- [ ] Admin and configuration tools

## Completion criteria

The system installs predictably, reports compatibility clearly, handles failures without corrupting project files, and produces useful diagnostics.

---

## 4. Capability Ideas for Later Evaluation

These ideas are intentionally not promises or immediate tasks. They describe directions the platform could explore.

### Natural-language drafting

- Create and edit geometry
- Build rooms and layouts
- Add dimensions and notes
- Place repeated objects
- Follow company layer standards

### Drawing review

- Find duplicate or disconnected objects
- Find missing dimensions
- Detect inconsistent layers or types
- Compare two drawing revisions
- Summarize changes

### Project automation

- Set up sheets and views
- Create standard details
- Rename objects
- Populate parameters
- Generate schedules and reports
- Prepare issue packages

### Visual understanding

- Read marked-up plans
- Trace plan images
- Recognize symbols
- Interpret screenshots
- Convert sketches into editable geometry

### 3D generation

- Convert 2D plans into basic buildings
- Create parametric walls and openings
- Place equipment from instructions
- Produce concept models
- Send models to Revit or Blender

### Fire protection assistance

- Place and count sprinklers
- Route pipe
- Build riser diagrams
- Check connectivity
- Review design data
- Assist with calculations and reports

---

## 5. Current Priority

The current priority is **planning**, not plugin development.

Before beginning the AutoCAD plugin, complete these planning deliverables:

1. Finalize the system architecture.
2. Decide the initial AutoCAD and .NET versions.
3. Confirm how Odysseus can call local tools.
4. Choose the first bridge protocol.
5. Draft command schema version 0.1.
6. Define the approval and safety policy.
7. Define the first ten plugin operations.
8. Draw an end-to-end sequence diagram.
9. Define the exact first milestone and test procedure.
10. Record unresolved decisions rather than hiding assumptions.

---

## 6. First Deliverable After Planning

The first implementation deliverable should be deliberately small:

> From Odysseus, request the active AutoCAD drawing name and units, then create one line with explicit coordinates, units, and layer information. Return the result and allow the entire action to be undone once.

This proves the core platform before work begins on complex drawing interpretation, Revit, AutoSPRINK, or 3D model generation.