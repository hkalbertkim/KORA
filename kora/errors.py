"""Structured runtime error taxonomy and failure contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Stage(str, Enum):
    IR = "IR"
    SCHEDULER = "SCHEDULER"
    DETERMINISTIC = "DETERMINISTIC"
    ADAPTER = "ADAPTER"
    VERIFY = "VERIFY"
    BUDGET = "BUDGET"
    UNKNOWN = "UNKNOWN"


class ErrorType(str, Enum):
    UNKNOWN = "UNKNOWN"
    INVALID_TASK = "INVALID_TASK"
    DAG_INVALID = "DAG_INVALID"
    DETERMINISTIC_EXEC_FAILED = "DETERMINISTIC_EXEC_FAILED"
    ADAPTER_FAILED = "ADAPTER_FAILED"
    OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"
    BUDGET_BREACH = "BUDGET_BREACH"
    ESCALATE_REQUIRED = "ESCALATE_REQUIRED"


@dataclass
class KoraRuntimeError(Exception):
    error_type: ErrorType
    stage: Stage
    details: Any
    task_id: str | None = None
    retryable: bool = False
    budget_breached: bool = False
    cause: Exception | None = None

    def to_failure_contract(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "stage": self.stage.value,
            "retryable": self.retryable,
            "budget_breached": self.budget_breached,
            "details": self.details,
            "task_id": self.task_id,
        }
