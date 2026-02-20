"""Task IR models, normalization, and validation for v0.1-min."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator


class Budget(BaseModel):
    """Execution budget limits."""

    max_time_ms: int = 1500
    max_tokens: int = 300
    max_retries: int = 1


class VerifyRuleRequired(BaseModel):
    """Requires paths to be present in output."""

    kind: Literal["required"]
    paths: list[str]


class VerifyRuleRange(BaseModel):
    """Constrains a numeric field to a min/max range."""

    kind: Literal["range"]
    path: str
    min: float
    max: float


VerifyRule = Annotated[VerifyRuleRequired | VerifyRuleRange, Field(discriminator="kind")]


class VerifySpec(BaseModel):
    """Verification settings for a task."""

    schema: dict[str, Any] | None = None
    rules: list[VerifyRule] = Field(default_factory=list)


class RunDetSpec(BaseModel):
    """Spec for deterministic handlers."""

    handler: str
    args: dict[str, Any] = Field(default_factory=dict)


class RunLlmSpec(BaseModel):
    """Spec for llm-backed handlers."""

    adapter: str
    input: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any]


class RunDet(BaseModel):
    kind: Literal["det"]
    spec: RunDetSpec


class RunLlm(BaseModel):
    kind: Literal["llm"]
    spec: RunLlmSpec


RunSpec = Annotated[RunDet | RunLlm, Field(discriminator="kind")]


class Policy(BaseModel):
    """Task execution policy."""

    budget: Budget | None = None
    on_fail: Literal["retry", "fail", "escalate"] = "fail"
    adaptive: "AdaptiveRoutingPolicy | None" = None


class AdaptiveRoutingPolicy(BaseModel):
    """Adaptive routing configuration knobs (schema only, no runtime behavior)."""

    routing_profile: Literal["latency", "cost", "reliability", "balanced"] = "balanced"
    min_confidence_to_stop: float = 0.85
    min_voi_to_escalate: float = 0.2
    max_escalations: int = 2
    escalation_order: list[str] = Field(default_factory=lambda: ["mini", "gate", "full"])
    stage_costs: dict[str, float] = Field(
        default_factory=lambda: {"mini": 1.0, "gate": 3.0, "full": 10.0}
    )
    use_voi: bool = True
    self_consistency_samples: int = 2
    self_consistency_enabled: bool = True
    self_consistency_max_tokens: int = 64
    self_consistency_min_next_cost: float = 200.0
    self_consistency_min_remaining_budget: float = 500.0

    def resolved(self) -> "AdaptiveRoutingPolicy":
        profile_defaults: dict[str, dict[str, Any]] = {
            "latency": {
                "use_voi": False,
                "self_consistency_enabled": False,
                "max_escalations": 0,
                "min_confidence_to_stop": 0.75,
            },
            "cost": {
                "use_voi": True,
                "min_voi_to_escalate": 0.2,
                "self_consistency_enabled": True,
                "self_consistency_samples": 2,
                "self_consistency_max_tokens": 64,
                "max_escalations": 2,
            },
            "reliability": {
                "use_voi": True,
                "min_voi_to_escalate": 0.1,
                "self_consistency_enabled": True,
                "self_consistency_samples": 3,
                "self_consistency_max_tokens": 96,
                "max_escalations": 2,
                "min_confidence_to_stop": 0.9,
            },
            "balanced": {
                "use_voi": True,
                "min_voi_to_escalate": 0.2,
                "self_consistency_enabled": True,
                "self_consistency_samples": 2,
                "self_consistency_max_tokens": 64,
                "max_escalations": 2,
            },
        }
        resolved_policy = self.model_copy(deep=True)
        explicitly_set = set(self.model_fields_set)
        defaults = profile_defaults.get(self.routing_profile, profile_defaults["balanced"])
        for field_name, default_value in defaults.items():
            if field_name not in explicitly_set:
                setattr(resolved_policy, field_name, default_value)
        return resolved_policy


class Task(BaseModel):
    """Task node in graph."""

    id: str
    type: str
    deps: list[str] = Field(default_factory=list)
    in_: dict[str, Any] = Field(alias="in", default_factory=dict)
    run: RunSpec
    verify: VerifySpec | None = None
    policy: Policy = Field(default_factory=Policy)
    tags: list[str] = Field(default_factory=list)


class GraphDefaults(BaseModel):
    budget: Budget = Field(default_factory=Budget)


class TaskGraph(BaseModel):
    """Task graph root model."""

    graph_id: str
    version: Literal["0.1"]
    root: str
    defaults: GraphDefaults
    tasks: list[Task]

    @model_validator(mode="after")
    def _ensure_non_empty_tasks(self) -> "TaskGraph":
        if not self.tasks:
            raise ValueError("tasks must contain at least one task")
        return self

    @classmethod
    def from_json(cls, path_or_str: str | Path) -> "TaskGraph":
        """Load a TaskGraph from a file path or raw JSON string."""
        if isinstance(path_or_str, Path):
            payload = json.loads(path_or_str.read_text(encoding="utf-8"))
            return cls.model_validate(payload)

        candidate_path = Path(path_or_str)
        if candidate_path.exists() and candidate_path.is_file():
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            return cls.model_validate(payload)

        payload = json.loads(path_or_str)
        return cls.model_validate(payload)


def normalize_graph(graph: TaskGraph) -> TaskGraph:
    """Apply inherited defaults and llm verify.schema inheritance."""
    normalized = graph.model_copy(deep=True)
    default_budget = normalized.defaults.budget

    for task in normalized.tasks:
        if task.policy.budget is None:
            task.policy.budget = default_budget.model_copy(deep=True)

        if task.run.kind == "llm":
            if task.verify is None:
                task.verify = VerifySpec(schema=task.run.spec.output_schema, rules=[])
            elif task.verify.schema is None:
                task.verify.schema = task.run.spec.output_schema

    return normalized


def validate_graph(graph: TaskGraph) -> None:
    """Validate task references and DAG constraints."""
    task_map: dict[str, Task] = {}
    for task in graph.tasks:
        if task.id in task_map:
            raise ValueError(f"duplicate task id: {task.id}")
        task_map[task.id] = task

    if graph.root not in task_map:
        raise ValueError(f"root task not found: {graph.root}")

    for task in graph.tasks:
        for dep in task.deps:
            if dep not in task_map:
                raise ValueError(f"task '{task.id}' depends on unknown task '{dep}'")

        if task.run.kind == "llm":
            if task.verify is None or task.verify.schema is None:
                raise ValueError(
                    f"llm task '{task.id}' must include verify.schema (directly or via normalization)"
                )

    from kora.scheduler import detect_cycle

    if detect_cycle(graph):
        raise ValueError("graph contains cycle; task graph must be a DAG")


__all__ = [
    "AdaptiveRoutingPolicy",
    "Budget",
    "Policy",
    "RunDetSpec",
    "RunLlmSpec",
    "RunSpec",
    "Task",
    "TaskGraph",
    "VerifyRuleRange",
    "VerifyRuleRequired",
    "VerifySpec",
    "normalize_graph",
    "validate_graph",
    "ValidationError",
]
