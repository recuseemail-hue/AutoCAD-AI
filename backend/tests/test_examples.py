import copy
import json
from pathlib import Path

from jsonschema import ValidationError, validate


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUEST_PATH = (
    PROJECT_ROOT
    / "examples"
    / "requests"
    / "create-line.json"
)

RESPONSE_PATH = (
    PROJECT_ROOT
    / "examples"
    / "responses"
    / "create-line-success.json"
)

SCHEMA_PATH = (
    PROJECT_ROOT
    / "schemas"
    / "v0.1"
    / "command.schema.json"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Could not find: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


request = load_json(REQUEST_PATH)
response = load_json(RESPONSE_PATH)
schema = load_json(SCHEMA_PATH)

# Test the valid command.
validate(instance=request, schema=schema)

assert request["command_id"] == response["command_id"]
assert response["status"] == "success"

print("Valid create-line command passed schema validation.")

# Create an intentionally invalid copy with the end point removed.
invalid_request = copy.deepcopy(request)
del invalid_request["parameters"]["end"]

try:
    validate(instance=invalid_request, schema=schema)
except ValidationError as error:
    print("Invalid command was correctly rejected.")
    print(f"Reason: {error.message}")
else:
    raise AssertionError("The invalid command should have been rejected.")

print("All command tests passed.")