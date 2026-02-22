"""Measure tail-full reduction from gate retrieval warming on a real-workload-like task."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kora.adapters.base import BaseAdapter
from kora import executor as executor_module
from kora.retrieval import build_retrieval_key
from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


N = 50
REQUEST = "User asks for a concise summary of cost variance risks in an AI support assistant rollout."
BASE_ADAPTER = "mock_retrieval_warm"
TASK_ID = "task_llm"
TASK_TYPE = "llm.answer"
INPUT_PAYLOAD = {"question": REQUEST}
TASK_TAGS = ["real-workload", "retrieval-warm-test"]


class MockMiniAdapter(BaseAdapter):
    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        del input, budget, output_schema
        return {
            "ok": True,
            "output": {"status": "ok", "task_id": task_id, "answer": "mini draft"},
            "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
            "meta": {"adapter": BASE_ADAPTER, "model": "mock-mini", "confidence": 0.1},
        }


class MockGateAdapter(BaseAdapter):
    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        del input, budget, output_schema
        return {
            "ok": True,
            "output": {"status": "ok", "task_id": task_id, "answer": "N/A"},
            "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
            "meta": {"adapter": f"{BASE_ADAPTER}:gate", "model": "mock-gate", "confidence": 0.2},
        }


class MockFullAdapter(BaseAdapter):
    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        del input, budget, output_schema
        return {
            "ok": True,
            "output": {
                "status": "ok",
                "task_id": task_id,
                "answer": "full answer: cost variance risks are demand volatility, policy drift, and handoff churn",
            },
            "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
            "meta": {"adapter": f"{BASE_ADAPTER}:full", "model": "mock-full", "confidence": 0.95},
        }


@dataclass
class BatchResult:
    enable_gate_retrieval: bool
    full_count: int
    n_runs: int
    tail_full_rate: float


def _build_graph(enable_gate_retrieval: bool) -> TaskGraph:
    payload = {
        "graph_id": "real-workload-retrieval-warm",
        "version": "0.1",
        "root": TASK_ID,
        "defaults": {"budget": {"max_time_ms": 20000, "max_tokens": 400, "max_retries": 1}},
        "tasks": [
            {
                "id": TASK_ID,
                "type": TASK_TYPE,
                "deps": [],
                "in": {},
                "run": {
                    "kind": "llm",
                    "spec": {
                        "adapter": BASE_ADAPTER,
                        "input": INPUT_PAYLOAD,
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "task_id": {"type": "string"},
                                "answer": {"type": "string"},
                            },
                            "required": ["status", "task_id", "answer"],
                        },
                    },
                },
                "verify": {
                    "schema": {"type": "object", "required": ["status", "task_id", "answer"]},
                    "rules": [],
                },
                "policy": {
                    "on_fail": "fail",
                    "adaptive": {
                        "routing_profile": "balanced",
                        "min_confidence_to_stop": 0.85,
                        "max_escalations": 2,
                        "escalation_order": ["gate", "full"],
                        "use_voi": False,
                        "enable_gate_retrieval": enable_gate_retrieval,
                    },
                },
                "tags": TASK_TAGS,
            }
        ],
    }
    graph = TaskGraph.model_validate(payload)
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    return normalized


def _run_batch(enable_gate_retrieval: bool, warm_before_each_run: bool) -> BatchResult:
    graph = _build_graph(enable_gate_retrieval=enable_gate_retrieval)
    retrieval_key = build_retrieval_key(TASK_TYPE, INPUT_PAYLOAD, TASK_TAGS)
    warmed_output = {
        "status": "ok",
        "task_id": TASK_ID,
        "answer": "full answer: cost variance risks are demand volatility, policy drift, and handoff churn",
    }

    tail_full_count = 0
    for _ in range(N):
        if warm_before_each_run:
            # Simulate retrieval cache warming from a known successful full output.
            executor_module.GATE_RETRIEVAL_STORE.put(retrieval_key, warmed_output)

        result = run_graph(graph)
        llm_events = [e for e in result.get("events", []) if e.get("task_id") == TASK_ID]
        if llm_events and llm_events[-1].get("meta", {}).get("adapter") == f"{BASE_ADAPTER}:full":
            tail_full_count += 1

    return BatchResult(
        enable_gate_retrieval=enable_gate_retrieval,
        full_count=tail_full_count,
        n_runs=N,
        tail_full_rate=tail_full_count / float(N),
    )


def main() -> None:
    old_mini = executor_module._AdapterRegistry.providers.get(BASE_ADAPTER)
    old_gate = executor_module._AdapterRegistry.providers.get(f"{BASE_ADAPTER}:gate")
    old_full = executor_module._AdapterRegistry.providers.get(f"{BASE_ADAPTER}:full")

    executor_module._AdapterRegistry.providers[BASE_ADAPTER] = MockMiniAdapter
    executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:gate"] = MockGateAdapter
    executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:full"] = MockFullAdapter

    executor_module.GATE_RETRIEVAL_STORE.clear()
    try:
        baseline = _run_batch(enable_gate_retrieval=False, warm_before_each_run=False)

        executor_module.GATE_RETRIEVAL_STORE.clear()
        retrieval_enabled = _run_batch(enable_gate_retrieval=True, warm_before_each_run=True)
    finally:
        executor_module.GATE_RETRIEVAL_STORE.clear()
        if old_mini is None:
            del executor_module._AdapterRegistry.providers[BASE_ADAPTER]
        else:
            executor_module._AdapterRegistry.providers[BASE_ADAPTER] = old_mini
        if old_gate is None:
            del executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:gate"]
        else:
            executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:gate"] = old_gate
        if old_full is None:
            del executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:full"]
        else:
            executor_module._AdapterRegistry.providers[f"{BASE_ADAPTER}:full"] = old_full

    print(f"N: {N}")
    print(f"task_type: {TASK_TYPE}")
    print(f"input_payload: {INPUT_PAYLOAD}")
    print(f"baseline enable_gate_retrieval: {baseline.enable_gate_retrieval}")
    print(f"baseline_full_count/N: {baseline.full_count}/{baseline.n_runs}")
    print(f"baseline_tail_full_rate: {baseline.tail_full_rate:.4f}")
    print(f"warmed enable_gate_retrieval: {retrieval_enabled.enable_gate_retrieval}")
    print(f"warmed_full_count/N: {retrieval_enabled.full_count}/{retrieval_enabled.n_runs}")
    print(f"retrieval_enabled_tail_full_rate: {retrieval_enabled.tail_full_rate:.4f}")
    print("warm_behavior: before each warmed run, retrieval store receives a put() of a known-good full output")


if __name__ == "__main__":
    main()
