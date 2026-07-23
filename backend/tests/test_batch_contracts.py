import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, validate

from backend.src.config import PROJECT_ROOT
from backend.src.contracts import (
    BATCH_MAX_ENTITIES,
    BATCH_MAX_POINTS,
    ContractValidationError,
    bridge_error_payload,
    get_batch_counts,
    load_schema,
    normalize_traceable_result,
    validate_command,
    validate_plugin_result,
    validate_result,
)


REQUESTS = PROJECT_ROOT / "examples" / "requests"
RESPONSES = PROJECT_ROOT / "examples" / "responses"


def load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def valid_execute_command() -> dict:
    return load_fixture(REQUESTS / "execute-batch-v0.4.json")


def valid_plugin_result() -> dict:
    return load_fixture(
        RESPONSES / "execute-batch-plugin-success-v0.4.json"
    )


def line_entity(index: int) -> dict:
    return {
        "client_entity_id": f"line-{index}",
        "entity_type": "line",
        "layer": "AI-BATCH",
        "create_layer_if_missing": True,
        "start": {"x": index * 2, "y": 0, "z": 0},
        "end": {"x": index * 2 + 1, "y": 0, "z": 0},
    }


def test_canonical_v04_requests_validate() -> None:
    validate_command(
        load_fixture(REQUESTS / "validate-batch-v0.4.json")
    )
    validate_command(valid_execute_command())


@pytest.mark.parametrize(
    "schema_name",
    [
        "command",
        "result",
        "plugin-result",
        "error",
    ],
)
def test_v04_schemas_are_valid_draft_202012(
    schema_name: str,
) -> None:
    Draft202012Validator.check_schema(load_schema("0.4", schema_name))


@pytest.mark.parametrize(
    "fixture_name",
    [
        "validate-batch-success-v0.4.json",
        "execute-batch-success-v0.4.json",
        "execute-batch-document-mismatch-v0.4.json",
        "execute-batch-rollback-v0.4.json",
    ],
)
def test_canonical_v04_normalized_results_validate(
    fixture_name: str,
) -> None:
    validate_result(load_fixture(RESPONSES / fixture_name))


def test_canonical_raw_plugin_result_validates_and_normalizes() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()

    validate_plugin_result(plugin_result)
    normalized = normalize_traceable_result(
        command,
        plugin_result,
        "2026-07-23T12:01:00.100Z",
    )

    validate_result(normalized)
    assert normalized["schema_version"] == "0.4"
    assert normalized["versions"] == {
        "bridge": "0.4.0",
        "plugin": "0.4.0",
    }
    assert normalized["data"]["created_count"] == 2


def test_v04_bridge_error_includes_complete_lifecycle() -> None:
    command = valid_execute_command()
    payload = bridge_error_payload(
        "AUTOCAD_DISCONNECTED",
        "AutoCAD is not connected.",
        command=command,
    )

    validate(
        instance=payload,
        schema=load_schema("0.4", "error"),
        format_checker=FormatChecker(),
    )
    assert payload["run_id"] == command["run_id"]
    assert payload["import_id"] == command["import_id"]
    assert payload["command_id"] == command["command_id"]


@pytest.mark.parametrize("entity_count", [1, BATCH_MAX_ENTITIES])
def test_v04_entity_count_boundaries_are_accepted(
    entity_count: int,
) -> None:
    command = valid_execute_command()
    command["parameters"]["entities"] = [
        line_entity(index)
        for index in range(entity_count)
    ]

    assert validate_command(command) == "0.4"
    assert get_batch_counts(command) == (entity_count, entity_count * 2)


@pytest.mark.parametrize("entity_count", [0, BATCH_MAX_ENTITIES + 1])
def test_v04_entity_count_outside_bounds_is_rejected(
    entity_count: int,
) -> None:
    command = valid_execute_command()
    command["parameters"]["entities"] = [
        line_entity(index)
        for index in range(entity_count)
    ]

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "BATCH_LIMIT_EXCEEDED"


def test_v04_exact_total_point_limit_is_accepted() -> None:
    command = valid_execute_command()
    polyline_point_count = BATCH_MAX_POINTS - 2
    command["parameters"]["entities"] = [
        line_entity(0),
        {
            "client_entity_id": "polyline-limit",
            "entity_type": "polyline",
            "layer": "AI-BATCH",
            "create_layer_if_missing": True,
            "vertices": [
                {"x": index, "y": 10, "z": 0}
                for index in range(polyline_point_count)
            ],
            "closed": False,
        },
    ]

    assert get_batch_counts(command)[1] == BATCH_MAX_POINTS
    assert validate_command(command) == "0.4"


def test_v04_total_point_limit_plus_one_is_rejected() -> None:
    command = valid_execute_command()
    command["parameters"]["entities"] = [
        line_entity(0),
        {
            "client_entity_id": "polyline-over-limit",
            "entity_type": "polyline",
            "layer": "AI-BATCH",
            "create_layer_if_missing": True,
            "vertices": [
                {"x": index, "y": 10, "z": 0}
                for index in range(BATCH_MAX_POINTS - 1)
            ],
            "closed": False,
        },
    ]

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "BATCH_LIMIT_EXCEEDED"


def test_v04_duplicate_client_entity_id_is_rejected() -> None:
    command = valid_execute_command()
    command["parameters"]["entities"][1]["client_entity_id"] = "line-001"

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "Duplicate client_entity_id" in str(error.value)


def test_v04_zero_length_line_is_rejected() -> None:
    command = valid_execute_command()
    command["parameters"]["entities"][0]["end"] = copy.deepcopy(
        command["parameters"]["entities"][0]["start"]
    )

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "zero length" in str(error.value)


def test_v04_non_finite_coordinate_is_rejected() -> None:
    command = valid_execute_command()
    command["parameters"]["entities"][0]["start"]["x"] = float("inf")

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "non-finite" in str(error.value)


def test_v04_duplicate_polyline_vertices_are_rejected() -> None:
    command = valid_execute_command()
    vertices = command["parameters"]["entities"][1]["vertices"]
    vertices[1] = copy.deepcopy(vertices[0])

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "duplicate consecutive vertices" in str(error.value)


def test_v04_closed_polyline_repeated_endpoint_is_rejected() -> None:
    command = valid_execute_command()
    polyline = command["parameters"]["entities"][1]
    polyline["closed"] = True
    polyline["vertices"].append(copy.deepcopy(polyline["vertices"][0]))

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "without repeating" in str(error.value)


def test_v04_closed_polyline_needs_three_distinct_vertices() -> None:
    command = valid_execute_command()
    polyline = command["parameters"]["entities"][1]
    polyline["closed"] = True
    polyline["vertices"] = polyline["vertices"][:2]

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_BATCH_GEOMETRY"
    assert "three distinct vertices" in str(error.value)


def test_v04_schema_rejects_unknown_entity_fields() -> None:
    command = valid_execute_command()
    command["parameters"]["entities"][0]["radius"] = 5

    with pytest.raises(ContractValidationError) as error:
        validate_command(command)

    assert error.value.code == "INVALID_COMMAND"


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("schema_version", "0.3"),
        ("run_id", "run-wrong"),
        ("import_id", "import-wrong"),
        ("command_id", "cmd-wrong"),
        ("application", "revit"),
        ("operation", "create_line"),
    ],
)
def test_v04_plugin_lifecycle_mismatch_is_rejected(
    field: str,
    wrong_value: str,
) -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result[field] = wrong_value

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert field in str(error.value)


def test_v04_validate_only_cannot_return_handles() -> None:
    command = load_fixture(REQUESTS / "validate-batch-v0.4.json")
    plugin_result = valid_plugin_result()
    plugin_result["command_id"] = command["command_id"]
    plugin_result["data"]["validate_only"] = True

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:00:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "Validate-only" in str(error.value)


def test_v04_success_requires_expected_document_identity() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result["document"]["name"] = "WrongDrawing.dwg"

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "document name" in str(error.value)


def test_v04_result_rejects_client_entity_mismatch() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result["data"]["entity_results"][1]["client_entity_id"] = "wrong"

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "one-to-one" in str(error.value)


def test_v04_result_rejects_handle_mismatch() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result["affected_objects"][1]["object_id"] = "FFFF"

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "handles" in str(error.value)


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("entity_result", "entity_type", "polyline", "type or layer"),
        ("entity_result", "layer", "WRONG", "type or layer"),
        ("affected_object", "object_type", "LWPOLYLINE", "type"),
    ],
)
def test_v04_result_rejects_entity_metadata_mismatch(
    target: str,
    field: str,
    value: str,
    message: str,
) -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    collection = (
        plugin_result["data"]["entity_results"]
        if target == "entity_result"
        else plugin_result["affected_objects"]
    )
    collection[0][field] = value

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert message in str(error.value)


def test_v04_execution_error_must_report_rollback() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result.update(
        {
            "status": "error",
            "message": "Batch execution failed.",
            "error": {
                "code": "BATCH_EXECUTION_FAILED",
                "message": "Batch execution failed.",
                "details": None,
            },
            "affected_objects": [],
            "undo_token": None,
        }
    )
    plugin_result["data"].update(
        {
            "created_count": 0,
            "rolled_back": False,
            "entity_results": [],
        }
    )

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "rolled_back true" in str(error.value)


def test_v04_execution_error_cannot_omit_rollback_data() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result.update(
        {
            "status": "error",
            "message": "Batch execution failed.",
            "error": {
                "code": "BATCH_EXECUTION_FAILED",
                "message": "Batch execution failed.",
                "details": None,
            },
            "affected_objects": [],
            "data": None,
            "undo_token": None,
        }
    )

    with pytest.raises(ContractValidationError) as error:
        normalize_traceable_result(
            command,
            plugin_result,
            "2026-07-23T12:01:00.100Z",
        )

    assert error.value.code == "INVALID_PLUGIN_RESPONSE"
    assert "rolled_back true" in str(error.value)


def test_v04_rollback_error_normalizes_without_created_objects() -> None:
    command = valid_execute_command()
    plugin_result = valid_plugin_result()
    plugin_result.update(
        {
            "status": "error",
            "message": "Batch rolled back.",
            "error": {
                "code": "BATCH_ROLLED_BACK",
                "message": "Batch rolled back.",
                "details": {"failed_client_entity_id": "polyline-001"},
            },
            "affected_objects": [],
            "undo_token": None,
        }
    )
    plugin_result["data"].update(
        {
            "created_count": 0,
            "rolled_back": True,
            "entity_results": [],
        }
    )

    normalized = normalize_traceable_result(
        command,
        plugin_result,
        "2026-07-23T12:01:00.100Z",
    )

    assert normalized["status"] == "error"
    assert normalized["data"]["rolled_back"] is True
    assert normalized["affected_objects"] == []
