from typing import Any

from kora.adapters.base import BaseAdapter
from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_run_graph_hello_kora() -> None:
    graph = TaskGraph.from_json("examples/hello_kora/graph.json")
    normalized = normalize_graph(graph)
    validate_graph(normalized)

    result = run_graph(normalized)
    assert result["ok"] is True
    final = result["final"]

    assert final["status"] == "ok"
    assert final["message"] == "hello from kora"


def test_run_graph_det_without_schema_succeeds() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "det-no-schema",
            "version": "0.1",
            "root": "task_echo",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_echo",
                    "type": "det.echo",
                    "deps": [],
                    "in": {"message": "hello"},
                    "run": {"kind": "det", "spec": {"handler": "echo", "args": {}}},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                }
            ],
        }
    )
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    assert result["ok"] is True
    assert result["final"]["message"] == "hello"


def test_run_graph_det_with_schema_still_verifies() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "det-with-schema",
            "version": "0.1",
            "root": "task_echo",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_echo",
                    "type": "det.echo",
                    "deps": [],
                    "in": {"message": "hello"},
                    "run": {"kind": "det", "spec": {"handler": "echo", "args": {}}},
                    "verify": {"schema": {"type": "object", "required": ["must_exist"]}, "rules": []},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                }
            ],
        }
    )
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    assert result["ok"] is False
    assert result["error"]["error_type"] == "OUTPUT_SCHEMA_INVALID"


def test_adaptive_confidence_escalates_through_adapter_order_until_confident() -> None:
    from kora import executor as executor_module

    class MockMiniAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockMiniAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "mini result",
                },
                "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini", "model": "mock-mini", "confidence": 0.1},
            }

    class MockGateAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockGateAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "gate result",
                },
                "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini:gate", "model": "mock-gate", "confidence": 0.2},
            }

    class MockFullAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockFullAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "full result",
                },
                "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini:full", "model": "mock-full", "confidence": 0.95},
            }

    graph = TaskGraph.model_validate(
        {
            "graph_id": "adaptive-multi-stage",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_llm",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_mini",
                            "input": {"question": "q"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {
                        "on_fail": "fail",
                        "adaptive": {
                            "min_confidence_to_stop": 0.85,
                            "max_escalations": 2,
                            "escalation_order": ["gate", "full"],
                            "use_voi": False,
                        },
                    },
                    "tags": [],
                }
            ],
        }
    )

    old_mini = executor_module._AdapterRegistry.providers.get("mock_mini")
    old_gate = executor_module._AdapterRegistry.providers.get("mock_mini:gate")
    old_full = executor_module._AdapterRegistry.providers.get("mock_mini:full")
    executor_module._AdapterRegistry.providers["mock_mini"] = MockMiniAdapter
    executor_module._AdapterRegistry.providers["mock_mini:gate"] = MockGateAdapter
    executor_module._AdapterRegistry.providers["mock_mini:full"] = MockFullAdapter
    MockMiniAdapter.call_count = 0
    MockGateAdapter.call_count = 0
    MockFullAdapter.call_count = 0
    try:
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        result = run_graph(normalized)
    finally:
        if old_mini is None:
            del executor_module._AdapterRegistry.providers["mock_mini"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini"] = old_mini
        if old_gate is None:
            del executor_module._AdapterRegistry.providers["mock_mini:gate"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini:gate"] = old_gate
        if old_full is None:
            del executor_module._AdapterRegistry.providers["mock_mini:full"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini:full"] = old_full

    assert result["ok"] is True
    llm_events = [event for event in result["events"] if event["task_id"] == "task_llm"]
    assert len(llm_events) == 3
    assert MockMiniAdapter.call_count + MockGateAdapter.call_count + MockFullAdapter.call_count == 3
    assert MockMiniAdapter.call_count == 1
    assert MockGateAdapter.call_count == 1
    assert MockFullAdapter.call_count == 1
    assert llm_events[0]["meta"]["adapter"] == "mock_mini"
    assert llm_events[1]["meta"]["adapter"] == "mock_mini:gate"
    assert llm_events[2]["meta"]["adapter"] == "mock_mini:full"
    assert llm_events[0]["escalation_step"] == 0
    assert llm_events[1]["escalation_step"] == 1
    assert llm_events[2]["escalation_step"] == 2
    assert llm_events[0]["meta"]["model"] == "mock-mini"
    assert llm_events[1]["meta"]["model"] == "mock-gate"
    assert llm_events[2]["meta"]["model"] == "mock-full"
    assert llm_events[-1]["meta"]["stop_reason"] == "confident_enough"


def test_adaptive_low_confidence_voi_too_low_stops_without_escalation() -> None:
    from kora import executor as executor_module

    class MockMiniAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockMiniAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "mini result",
                },
                "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini", "model": "mock-mini", "confidence": 0.1},
            }

    graph = TaskGraph.model_validate(
        {
            "graph_id": "adaptive-voi-too-low",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_llm",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_mini",
                            "input": {"question": "q"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {
                        "on_fail": "fail",
                        "adaptive": {
                            "min_confidence_to_stop": 0.85,
                            "min_voi_to_escalate": 0.2,
                            "max_escalations": 2,
                            "escalation_order": ["full"],
                            "stage_costs": {"full": 10.0},
                            "use_voi": True,
                        },
                    },
                    "tags": [],
                }
            ],
        }
    )

    old_mini = executor_module._AdapterRegistry.providers.get("mock_mini")
    executor_module._AdapterRegistry.providers["mock_mini"] = MockMiniAdapter
    MockMiniAdapter.call_count = 0
    try:
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        result = run_graph(normalized)
    finally:
        if old_mini is None:
            del executor_module._AdapterRegistry.providers["mock_mini"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini"] = old_mini

    assert result["ok"] is True
    llm_events = [event for event in result["events"] if event["task_id"] == "task_llm"]
    assert len(llm_events) == 1
    assert MockMiniAdapter.call_count == 1
    meta = llm_events[0]["meta"]
    assert meta["stop_reason"] == "voi_too_low"
    assert meta["escalate_recommended"] is False
    assert meta["uncertainty"] == 0.9
    assert meta["voi"] == 0.09


def test_adaptive_voi_uses_runtime_estimated_cost_when_policy_cost_missing() -> None:
    from kora import executor as executor_module

    class MockGateAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockGateAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "gate result",
                },
                "usage": {"tokens_in": 1000, "tokens_out": 1000},
                "meta": {"adapter": "mock_mini:gate", "model": "mock-gate", "confidence": 0.99},
            }

    class MockMiniAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockMiniAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "mini result",
                },
                "usage": {"tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini", "model": "mock-mini", "confidence": 0.1},
            }

    graph = TaskGraph.model_validate(
        {
            "graph_id": "adaptive-voi-runtime-estimate",
            "version": "0.1",
            "root": "task_target",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_warm_gate",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_mini:gate",
                            "input": {"question": "warm"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                },
                {
                    "id": "task_target",
                    "type": "llm.answer",
                    "deps": ["task_warm_gate"],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_mini",
                            "input": {"question": "q"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {
                        "on_fail": "fail",
                        "adaptive": {
                            "min_confidence_to_stop": 0.85,
                            "min_voi_to_escalate": 0.2,
                            "max_escalations": 1,
                            "escalation_order": ["gate"],
                            "stage_costs": {"mini": 1.0, "full": 10.0},
                            "use_voi": True,
                        },
                    },
                    "tags": [],
                },
            ],
        }
    )

    old_mini = executor_module._AdapterRegistry.providers.get("mock_mini")
    old_gate = executor_module._AdapterRegistry.providers.get("mock_mini:gate")
    executor_module._AdapterRegistry.providers["mock_mini"] = MockMiniAdapter
    executor_module._AdapterRegistry.providers["mock_mini:gate"] = MockGateAdapter
    MockMiniAdapter.call_count = 0
    MockGateAdapter.call_count = 0
    try:
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        result = run_graph(normalized)
    finally:
        if old_mini is None:
            del executor_module._AdapterRegistry.providers["mock_mini"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini"] = old_mini
        if old_gate is None:
            del executor_module._AdapterRegistry.providers["mock_mini:gate"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini:gate"] = old_gate

    assert result["ok"] is True
    assert MockGateAdapter.call_count == 1
    assert MockMiniAdapter.call_count == 1
    target_events = [event for event in result["events"] if event["task_id"] == "task_target"]
    assert len(target_events) == 1
    meta = target_events[0]["meta"]
    assert meta["cost_units"] == 2.0
    assert meta["stop_reason"] == "voi_too_low"
    assert meta["estimated_next_cost"] > 100.0


def test_adaptive_budget_remaining_low_blocks_escalation() -> None:
    from kora import executor as executor_module

    class MockMiniAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            MockMiniAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "mini result",
                },
                "usage": {"tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "mock_mini", "model": "mock-mini", "confidence": 0.1},
            }

    graph = TaskGraph.model_validate(
        {
            "graph_id": "adaptive-budget-low",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_llm",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_mini",
                            "input": {"question": "q"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {
                        "budget": {"max_time_ms": 1500, "max_tokens": 1, "max_retries": 1},
                        "on_fail": "fail",
                        "adaptive": {
                            "min_confidence_to_stop": 0.85,
                            "min_voi_to_escalate": 0.01,
                            "max_escalations": 1,
                            "escalation_order": ["gate"],
                            "stage_costs": {"gate": 2.0},
                            "use_voi": True,
                        },
                    },
                    "tags": [],
                }
            ],
        }
    )

    old_mini = executor_module._AdapterRegistry.providers.get("mock_mini")
    executor_module._AdapterRegistry.providers["mock_mini"] = MockMiniAdapter
    MockMiniAdapter.call_count = 0
    try:
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        result = run_graph(normalized)
    finally:
        if old_mini is None:
            del executor_module._AdapterRegistry.providers["mock_mini"]
        else:
            executor_module._AdapterRegistry.providers["mock_mini"] = old_mini

    assert result["ok"] is True
    llm_events = [event for event in result["events"] if event["task_id"] == "task_llm"]
    assert len(llm_events) == 1
    assert MockMiniAdapter.call_count == 1
    meta = llm_events[0]["meta"]
    assert meta["stop_reason"] == "budget_remaining_low"
    assert meta["escalate_recommended"] is False
