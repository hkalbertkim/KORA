"""Verification hooks and rule evaluation for v0.1-alpha."""

from __future__ import annotations

from typing import Any

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as jsonschema_validate

from kora.task_ir import Task


def validate_schema(output: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate output payload against a JSON schema."""
    try:
        jsonschema_validate(instance=output, schema=schema)
    except JSONSchemaValidationError as exc:
        raise ValueError(f"schema validation failed: {exc.message}") from exc


def apply_rules(output: dict[str, Any], rules: list[Any]) -> None:
    """Apply minimal v0.1 verification rules to an output payload."""
    for rule in rules:
        if rule.kind == "required":
            missing = [path for path in rule.paths if path not in output]
            if missing:
                raise ValueError(f"required rule failed; missing keys: {missing}")
        elif rule.kind == "range":
            # TODO(v0.1): extend path handling beyond top-level numeric keys.
            value = output.get(rule.path)
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                raise ValueError(f"range rule failed; '{rule.path}' is not numeric")
            if value < rule.min or value > rule.max:
                raise ValueError(
                    f"range rule failed; {rule.path}={value} outside [{rule.min}, {rule.max}]"
                )


def verify_output(task: Task, output: dict[str, Any]) -> None:
    """Validate task output with schema and rules."""
    if task.verify is None or task.verify.schema is None:
        raise ValueError(f"task '{task.id}' missing verify.schema")

    validate_schema(output, task.verify.schema)
    apply_rules(output, task.verify.rules)
