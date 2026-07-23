# AutoCAD-AI PDF-to-CAD Implementation Plan

Last updated: July 22, 2026.

## Product Goal

Build a reviewable plan-to-CAD copilot that can inspect engineering PDFs,
extract precise candidate geometry, classify likely engineering meaning, show
the proposed work to an engineer, and commit only approved entities to
AutoCAD in one reversible operation.

The system is an engineering assistant, not an autonomous engineer. AI may
interpret intent and classify ambiguous content. Deterministic code owns
coordinates, scale, validation, transactions, verification, and recovery.

## Confirmed Baseline

The first live vertical slice is complete and committed to `main`:

```text
Odysseus
  -> AutoCAD-AI MCP server
  -> FastAPI bridge
  -> local AutoCAD plugin HTTP endpoint
  -> native AutoCAD line
  -> correlated result
```

The real plugin created a line successfully in AutoCAD. This is the protected
baseline for all later work.

## Architecture Rules

1. AI never writes directly to AutoCAD.
2. No drawing mutation occurs without a validated command.
3. PDF-derived writes require a recorded review decision.
4. Every write is atomic and reversible.
5. Every entity retains source-document provenance.
6. Network contracts are versioned independently of Python and C# classes.
7. New schema versions remain compatible until an explicit migration removes
   the older version.
8. Intermediate extraction, analysis, review, import, and verification
   artifacts remain inspectable.
9. Domain calculations and code rules live in deterministic, versioned
   modules rather than prompts.
10. Each milestone ends in a testable vertical slice.

## Target Workflow

```text
PDF upload
  -> document inspection
  -> vector extraction or raster/OCR processing
  -> AI semantic classification
  -> canonical Plan IR
  -> deterministic geometry validation
  -> visual review overlay
  -> engineer approval
  -> atomic AutoCAD batch
  -> handle and geometry verification
  -> import report and undo
```

## Milestone 1 - Contracts and Observability

Status: **Complete - live verified**

Goal:

> Introduce traceable, versioned command lifecycles without breaking the
> confirmed schema-v0.1 line workflow.

Deliverables:

- [x] Preserve schema v0.1 as a supported compatibility contract.
- [x] Add schema v0.2 commands with `run_id`, nullable `import_id`, and
  `submitted_at`.
- [x] Add a formal schema v0.2 command-result contract.
- [x] Add a formal schema v0.2 bridge-error contract.
- [x] Include bridge and plugin versions in v0.2 results.
- [x] Include active-document identity in v0.2 results.
- [x] Add structured error codes across bridge and plugin failures.
- [x] Add bridge-received and completed timestamps.
- [x] Centralize plugin URL, timeouts, log path, and log rotation settings.
- [x] Add structured JSONL command lifecycle logging.
- [x] Log identifiers, operation, status, duration, and error code without
  logging full drawing payloads.
- [x] Validate v0.1 and v0.2 commands with version-selected schemas.
- [x] Validate normalized v0.2 results before returning them.
- [x] Add contract fixtures and compatibility tests.
- [x] Update MCP line creation to emit v0.2 commands.
- [x] Update documentation and version reporting.

Definition of done:

1. Existing v0.1 request fixtures still validate and route successfully.
2. A v0.2 line request returns a schema-valid v0.2 result.
3. The result contains matching `run_id`, `command_id`, versions, timestamps,
   and active-document identity.
4. Failures return stable machine-readable error codes.
5. The command log can trace a request from acceptance to completion without
   storing complete geometry.
6. Python tests pass and the AutoCAD plugin builds successfully.

Implementation record:

- Branch: `Luke/PDFRead`
- Protected baseline commit: `3e83d70`
- Milestone 1 feature commit: `91b7547`
- Bridge version: `0.2.0`
- Plugin version: `0.2.0`
- Rebuilt DLL: `Plugin/AutoCadAIPlugin/dist/AutoCadAIPlugin.dll`
- Automated verification: `30 passed`
- Plugin build: succeeded with zero warnings and zero errors
- Live verification: successful v0.2 command
  `cmd-65426dfa-66ca-49e9-9734-1adca8a21a15` in run
  `run-4897b23e-9c1b-4c71-af5e-940b263b846c`.

## Milestone 2 - Read-Only AutoCAD Toolkit

Status: **Complete - live verified**

Contract strategy:

- Freeze the verified create-line contract at schema v0.2.
- Add schema v0.3 for read-only commands and results.
- Keep v0.1 and v0.2 supported throughout this milestone.

Add:

- [x] `get_drawing_context`
- [x] `get_active_document`
- [x] `get_drawing_units`
- [x] `get_current_coordinate_system`
- [x] `get_drawing_extents`
- [x] `list_layers`
- [x] `get_selected_entities`
- [x] `get_entities_in_window`
- [x] `get_entity_properties`
- [x] `find_entities_by_import_id`
- [x] Bounded layer and entity query results.
- [x] World-space window validation.
- [x] Type-specific properties for lines, circles, arcs, polylines, and text.
- [x] AutoCAD-AI XData provenance on newly created v0.2 lines.
- [x] Handle and import-ID lookup.
- [x] Schema, API, MCP, compatibility, and correlation tests.
- [x] AutoCAD plugin release build.

Definition of done:

> Odysseus can accurately describe the current drawing without changing it.

Extended live coverage, not a completion blocker:

> Exercise the world-space window and import-ID lookups on representative
> project drawings before relying on them in the PDF import workflow.

Implementation record:

- Bridge version: `0.3.0`
- Plugin version: `0.3.0`
- Automated verification: `48 passed`
- Plugin build: succeeded with zero warnings and zero errors
- Rebuilt DLL: `Plugin/AutoCadAIPlugin/dist/AutoCadAIPlugin.dll`
- DLL SHA-256:
  `6904CAE4549FF3203CC2291346EBA0C42F1D2C5CA0F2F3169E56F9DA601A55F0`
- Live direct verification:
  - `get_drawing_context` succeeded against `Floor Plan Sample.dwg`;
  - `list_layers` returned all 30 layers;
  - bridge and plugin both reported version `0.3.0`;
  - the MCP server advertised all 13 expected tools.
- Live Odysseus verification:
  - `get_drawing_context` and `list_layers` completed successfully;
  - `get_selected_entities` returned line handle `EEE`;
  - `get_entity_properties` returned the line's layer, extents, endpoints,
    length, linetype, lineweight, color, and visibility;
  - all four operations completed as correlated schema-v0.3 commands.

## Milestone 3 - Atomic Batch Geometry

Status: **Ready for two-person parallel implementation**

Goal:

> Accept a validated batch of lines and polylines, preview it without drawing,
> and then create the complete batch in one traceable AutoCAD transaction. Any
> failure must leave the drawing unchanged.

### Milestone 3 Start Gate

The current Milestone 2 worktree must be committed, pushed, and clean before
creating Milestone 3 branches. Do not branch directly from commit `91b7547`;
that commit does not contain the uncommitted Milestone 2 implementation.

Required sequence:

1. Run the full Milestone 2 test and build commands.
2. Commit and push the verified Milestone 2 state.
3. Record that commit as `M3_BASE_SHA`.
4. Create an integration branch from exactly `M3_BASE_SHA`.
5. Complete the contract-freeze commit below on the integration branch.
6. Create both workstream branches from that same contract-freeze commit.
7. Record the base SHA, contract SHA, both owners, and integration owner here.

Ownership record:

- `M3_BASE_SHA`: pending Milestone 2 commit
- Contract-freeze SHA: pending
- Workstream A owner: Luke + Codex
- Workstream B owner: teammate
- Integration owner: pending team confirmation

Suggested branches:

```text
feature/m3-atomic-batch          # integration only
Luke/m3-platform                 # Workstream A
teammate/m3-autocad-plugin       # Workstream B
```

Each person must use a separate clone or Git worktree. Do not work in the same
filesystem checkout.

### Contract-Freeze Checkpoint

This is a short shared checkpoint before parallel implementation, not a third
workstream. Freeze and commit:

- `schemas/v0.4/command.schema.json`
- `schemas/v0.4/result.schema.json`
- `schemas/v0.4/error.schema.json`
- canonical success, validate-only, document-mismatch, and rollback fixtures;
- `docs/contracts/v0.4-atomic-batch.md`

Both owners must approve the exact fixtures and error codes before branching.
After the split, Workstream A is the sole schema owner. If a contract change
becomes unavoidable:

1. stop both workstreams at a clean commit;
2. make and review the schema change on the integration branch;
3. merge the integration branch into both workstream branches;
4. update fixtures before implementation resumes.

Do not independently reinterpret or copy-edit the contract in the plugin.

### Frozen v0.4 Contract Scope

The v0.4 command operation is `execute_batch`. A single polyline is represented
as a one-entity batch rather than a separate network operation.

Required command semantics:

- non-null `run_id`, `import_id`, and `command_id`;
- `submitted_at`, `application: autocad`, and `requires_approval: false`;
- `validate_only`;
- expected document name and optional AutoCAD fingerprint GUID;
- explicit units and `coordinate_system: world`;
- 1 to 500 entities and no more than 50,000 total points;
- unique `client_entity_id` for every entity;
- entity types `line` and `polyline`;
- explicit layer and `create_layer_if_missing` policy per entity;
- line start/end points;
- polyline vertices and `closed`;
- finite coordinates and no zero-length line or consecutive duplicate
  polyline vertices.

Required result semantics:

- lifecycle IDs and bridge/plugin versions;
- matched active-document identity;
- `validate_only`, validated count, created count, and rollback state;
- one result entry per `client_entity_id`;
- real AutoCAD handles after execution;
- no handles and `undo_token: null` for validate-only;
- a single batch undo token after execution;
- stable error codes including:
  - `DOCUMENT_MISMATCH`
  - `BATCH_LIMIT_EXCEEDED`
  - `INVALID_BATCH_GEOMETRY`
  - `LAYER_POLICY_ERROR`
  - `DUPLICATE_COMMAND`
  - `BATCH_EXECUTION_FAILED`
  - `BATCH_ROLLED_BACK`

Retry policy:

> Reusing an executed `command_id` must never create duplicate geometry. The
> plugin must detect the existing command provenance and return
> `DUPLICATE_COMMAND` or the previously correlated result.

### Workstream A - Contract, Bridge, MCP, and Python Tests

Suggested owner: **Luke + Codex**

Exclusive file ownership:

```text
schemas/v0.4/**
examples/requests/*batch*v0.4.json
examples/responses/*batch*v0.4.json
backend/src/**
backend/tests/**
requirements*.txt
```

Do not edit or build anything under `Plugin/`.

Deliverables:

- [ ] Add v0.4 to bridge version negotiation without changing v0.1-v0.3.
- [ ] Add version-selected validation for commands, results, and errors.
- [ ] Add deterministic semantic validation for batch and point limits.
- [ ] Add `validate_autocad_batch`.
- [ ] Add `execute_autocad_batch`.
- [ ] Keep geometry payloads out of structured lifecycle logs.
- [ ] Normalize validate-only, success, plugin-error, and rollback results.
- [ ] Preserve lifecycle and `client_entity_id` correlation.
- [ ] Add fake-plugin API tests for atomic success and every error class.
- [ ] Test timeouts, malformed results, mismatched IDs, and duplicate retries.
- [ ] Add boundary tests for 1/500/501 entities and 50,000/50,001 points.
- [ ] Add positive and negative line/polyline fixtures.
- [ ] Prove all existing Milestone 1 and 2 tests still pass.

Workstream A test gate:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q backend
git diff --check
```

The Workstream A pull request must contain no paths under `Plugin/`.

### Workstream B - Native AutoCAD Batch Executor

Suggested owner: **AutoCAD plugin teammate**

Exclusive file ownership:

```text
Plugin/AutoCadAIPlugin/**
Plugin/AutoCadAIPlugin.Tests/**
```

Do not edit `backend/`, `schemas/`, root examples, or shared documentation.
Consume the frozen v0.4 fixtures exactly as approved.

Deliverables:

- [ ] Add v0.4 request and result DTOs without regressing v0.1-v0.3.
- [ ] Separate pure batch validation/planning from AutoCAD database writes.
- [ ] Validate the active document name and optional fingerprint.
- [ ] Validate every layer and entity before opening a write transaction.
- [ ] Implement native `Line` and `Polyline` creation.
- [ ] Make validate-only use read-mode transactions and create nothing.
- [ ] Enforce the hard entity and total-point limits independently.
- [ ] Execute the complete batch in one AutoCAD transaction.
- [ ] Abort the transaction on the first execution failure.
- [ ] Attach run, import, command, and `client_entity_id` XData to every entity.
- [ ] Return every created handle correlated to `client_entity_id`.
- [ ] Detect repeated executed `command_id` values before creating geometry.
- [ ] Group the committed batch into one native AutoCAD undo action.
- [ ] Provide a test-only, non-network failure hook for proving transaction
  rollback after N staged entities; it must be unavailable in the Release DLL.
- [ ] Add C# tests for pure validation and planning wherever AutoCAD runtime
  access is not required.
- [ ] Rebuild the release DLL and update only plugin-owned build artifacts.

Workstream B test gate:

```powershell
dotnet test .\Plugin\AutoCadAIPlugin.Tests\AutoCadAIPlugin.Tests.csproj
dotnet build .\Plugin\AutoCadAIPlugin\AutoCadAIPlugin.csproj `
  --configuration Release --no-restore
```

The Workstream B pull request must contain no paths under `backend/`,
`schemas/`, `examples/requests`, `examples/responses`, or shared documentation.

### File Ownership and Merge-Conflict Controls

| Path | Owner during parallel work |
|---|---|
| `schemas/v0.4/**` | Workstream A only |
| `examples/requests/**`, `examples/responses/**` | Workstream A only |
| `backend/**` | Workstream A only |
| `requirements*.txt` | Workstream A only |
| `Plugin/**` including tracked `bin/`, `obj/`, and `dist/` | Workstream B only |
| `Implementation Plan.md`, `README.md`, `docs/**` | Integration owner only after both merges |

Additional controls:

- Do not run repository-wide formatters.
- Do not rename or relocate shared folders during this milestone.
- Do not commit build artifacts from Workstream A.
- Only Workstream B may regenerate the tracked plugin binaries.
- Keep commits scoped to one deliverable.
- Before opening each pull request, compare changed paths with
  `git diff --name-only M3_BASE_SHA...HEAD`.
- Any file outside the assigned ownership area must be reverted or explicitly
  coordinated before review.

### Integration and Merge Order

1. Review both workstream pull requests independently against the frozen
   contract.
2. Merge Workstream A into `feature/m3-atomic-batch`.
3. Merge Workstream B into `feature/m3-atomic-batch`.
4. The integration owner resolves contract issues by changing the owning
   workstream, not by applying an unreviewed merge-only patch.
5. Run the complete integration gate.
6. Update shared documentation and the implementation record only after all
   tests pass.
7. Merge the integration branch to the project branch/main only after live
   AutoCAD acceptance passes.

Because the two workstreams have disjoint file ownership, either code branch
can technically merge first. The order above makes the bridge-side contract
tests available before the plugin is introduced.

### Combined Automated Test Gate

- [ ] All pre-existing Python tests pass.
- [ ] All new v0.4 Python contract/API/MCP tests pass.
- [ ] All pure C# validator/planner tests pass.
- [ ] AutoCAD plugin Release build completes with zero errors.
- [ ] Canonical v0.4 fixtures validate against the frozen JSON schemas.
- [ ] Plugin-produced results validate through the Python result validator.
- [ ] No lifecycle mismatch is silently normalized.
- [ ] Logs contain identifiers, counts, status, duration, and errors but not
  complete geometry.
- [ ] `git diff --check` passes.
- [ ] Changed-file ownership checks pass for both workstreams.

### Live AutoCAD Acceptance Matrix

Use a disposable drawing and record entity counts before and after every test.

1. **Validate only:** a valid mixed line/polyline batch reports valid and
   creates zero entities.
2. **Wrong document:** expected-document mismatch creates zero entities.
3. **Invalid first entity:** validation fails and creates zero entities.
4. **Invalid last entity:** proves full preflight; creates zero entities.
5. **Missing locked-down layer:** policy failure creates zero entities.
6. **Mid-execution failure:** using the test-only failure hook, transaction
   aborts and creates zero entities; confirm the hook is absent from Release.
7. **Boundary limits:** 500 entities is accepted; 501 is rejected.
8. **Mixed success:** exact requested line/polyline count is created.
9. **Geometry verification:** read back every handle and compare type, layer,
   coordinates, closed state, and drawing-unit conversion.
10. **Provenance verification:** `find_entities_by_import_id` finds the complete
    batch and every entity carries its `client_entity_id`.
11. **Duplicate retry:** resubmitting the same `command_id` creates nothing.
12. **Undo:** one AutoCAD `UNDO` removes the entire successful batch and
    nothing outside it.
13. **Restart:** repeat validate and execute after restarting AutoCAD, bridge,
    MCP, and Odysseus.

Save the command, normalized result, before/after counts, returned handles,
undo result, plugin version, and DLL hash in the implementation record.

Definition of done:

> A test batch either creates every requested entity or leaves the drawing
> unchanged. Validation-only creates nothing, repeated commands cannot create
> duplicates, every created handle and provenance record is verified, and one
> undo removes the complete batch.

## Milestone 4 - PDF Ingestion

Status: **Planned**

Add local document storage, hashing, page metadata, page rendering, text
availability checks, vector-path counts, embedded-image counts, and
vector/raster/mixed page classification.

Suggested artifact layout:

```text
data/runs/{run_id}/
  source.pdf
  metadata.json
  pages/
  extraction/
  analysis/
  review/
  import/
```

## Milestone 5 - Vector PDF Extraction

Status: **Planned**

Extract positioned text and vector paths, normalize page rotation, calibrate
scale, transform PDF coordinates, remove duplicate and tiny segments, join
collinear geometry, and create the first canonical Plan IR.

Definition of done:

> A known vector fixture produces expected coordinates within a defined
> tolerance.

## Milestone 6 - AI Semantic Classification

Status: **Planned**

Use page images, extracted text, candidate paths, and nearby labels to assign a
limited semantic vocabulary, suggested layer, confidence, evidence, warnings,
and review requirements. AI annotations must reference deterministic candidate
IDs rather than replacing their coordinates.

## Milestone 7 - Visual Review Interface

Status: **Planned**

Build a local PDF viewer with geometry overlays, confidence filtering,
accept/reject controls, reclassification, layer assignment, endpoint editing,
scale calibration, warnings, and immutable review revisions.

Definition of done:

> No PDF-derived candidate can enter an import manifest without a recorded
> review decision.

## Milestone 8 - End-to-End Vector Import

Status: **Planned**

Convert accepted candidates into an import manifest, validate the complete
batch, commit it in AutoCAD, verify handles and coordinates, create an import
report, and undo the entire import.

## Milestone 9 - Scanned PDFs

Status: **Planned**

Add high-resolution rendering, OCR, line and contour detection, tiled
processing, tile stitching, vision-assisted classification, and stricter
confidence/review thresholds.

## Milestone 10 - Domain Packs

Status: **Planned**

Civil candidates:

- utilities;
- parcel and easement lines;
- curb, sidewalk, striping, and drainage linework;
- existing/demolition/proposed classification;
- reviewed length and area takeoffs;
- gap and overlap detection.

Mechanical candidates:

- pipe and duct centerlines;
- equipment tags and approved blocks;
- system-layer mapping;
- fitting candidates;
- connectivity checks;
- schedule extraction;
- reviewed length and count takeoffs.

Native Civil 3D objects require a separate Civil 3D adapter. Engineering
calculations and compliance decisions require deterministic rule modules and
qualified review.

## Milestone 11 - Production Hardening

Status: **Planned**

Add authentication, sensitive-document controls, installers, compatibility
checks, crash recovery, structured diagnostics, performance limits, large-plan
testing, data-retention controls, and a supported plugin/application matrix.

## Testing Strategy

1. Contract tests ensure Python and C# share compatible request and result
   semantics.
2. Geometry fixtures measure coordinate and transformation accuracy.
3. AI evaluations measure classification precision, recall, and uncertainty.
4. End-to-end AutoCAD tests verify native object types, handles, layers,
   coordinates, rollback, and undo.
5. Golden PDF/Plan-IR/DWG fixtures protect refactors.

Metrics:

- coordinate error;
- semantic precision and recall;
- false and missed geometry rates;
- engineer correction time;
- import and rollback success rates;
- time saved per sheet;
- processing latency and AI cost per sheet.
