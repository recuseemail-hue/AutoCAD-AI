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

Status: **Implemented - live v0.2 verification pending**

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
- Bridge version: `0.2.0`
- Plugin version: `0.2.0`
- Rebuilt DLL: `Plugin/AutoCadAIPlugin/dist/AutoCadAIPlugin.dll`
- Automated verification: `30 passed`
- Plugin build: succeeded with zero warnings and zero errors
- Remaining manual gate: load the rebuilt DLL and confirm one v0.2 line result
  contains the matching run and command IDs, versions, timestamps, document
  identity, and affected object handle.

## Milestone 2 - Read-Only AutoCAD Toolkit

Status: **Planned**

Add:

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

Definition of done:

> Odysseus can accurately describe the current drawing without changing it.

## Milestone 3 - Atomic Batch Geometry

Status: **Planned**

Add:

- `create_polyline`
- initial line and polyline batch format;
- validate-only mode;
- expected-document checks;
- entity-count limits;
- one AutoCAD transaction per batch;
- import metadata attached to created objects;
- complete result handles;
- complete rollback and undo.

Definition of done:

> A test batch either creates every requested entity or leaves the drawing
> unchanged.

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
