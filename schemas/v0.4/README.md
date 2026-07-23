# AutoCAD-AI v0.4 Atomic Batch Contract

Schema v0.4 freezes the wire format shared by the Python bridge and AutoCAD
plugin for Milestone 3.

- `command.schema.json` defines validate-only and execute requests.
- `plugin-result.schema.json` defines the raw response returned by the plugin.
- `result.schema.json` defines the normalized response returned by the bridge.
- `error.schema.json` defines failures produced before a plugin result exists.

Normative limits:

- 1 to 500 entities per batch;
- no more than 50,000 total points;
- unique `client_entity_id` values;
- finite coordinates;
- no zero-length lines;
- no consecutive duplicate polyline vertices;
- closed polylines need at least three distinct vertices.

The plugin must independently enforce these rules. Reusing an executed
`command_id` must not create duplicate geometry.

## Command behavior

The network operation is always `execute_batch`.

- `parameters.validate_only: true` performs the complete document, layer,
  limit, unit, and geometry preflight but opens no write transaction.
- `parameters.validate_only: false` executes only after the same preflight
  passes.
- `expected_document.name` is required and compared case-insensitively.
- When `expected_document.fingerprint_guid` is non-null, it must also match.
- `import_id` is required and is attached to every created entity.
- Every entity must preserve its `client_entity_id` through result correlation
  and XData provenance.

The Python MCP surface exposes separate `validate_autocad_batch` and
`execute_autocad_batch` tools. Both produce this same wire command with a
different `validate_only` value.

## Raw plugin result

The plugin returns `plugin-result.schema.json`, including:

- the unchanged schema, run, import, command, application, and operation IDs;
- `plugin_version` and `completed_at`;
- the active document name and fingerprint;
- `data.validate_only`, validation/creation counts, rollback state, and one
  entity result per `client_entity_id`;
- one `affected_objects` entry and real AutoCAD handle per executed entity;
- one batch `undo_token` for execution, or null for validation/errors.

For a successful validate-only result:

- every entity status is `validated`;
- all object IDs are null;
- `created_count` is zero;
- `affected_objects` is empty;
- `undo_token` is null.

For a successful execution:

- every entity status is `created`;
- every entity and affected-object handle matches;
- `validated_count` and `created_count` equal the request entity count;
- `rolled_back` is false;
- `undo_token` is non-empty.

For any error:

- no affected objects or undo token may be returned;
- `created_count` is zero when data is present;
- `BATCH_EXECUTION_FAILED` and `BATCH_ROLLED_BACK` require
  `rolled_back: true`.

Suggested HTTP statuses:

- `400` malformed or invalid geometry;
- `409` document mismatch, layer-policy conflict, or duplicate command;
- `413` entity/point/request-size limit exceeded;
- `500` execution failure that was rolled back;
- `503` no active document or AutoCAD idle timeout.

Canonical fixtures live under `examples/requests` and `examples/responses`.
The file `execute-batch-plugin-success-v0.4.json` is the direct C#
serialization target; the other success files are normalized bridge results.
