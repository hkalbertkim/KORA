"""Direct same-device baseline: no worker routing or result reuse.

This measures the benchmark adapter boundary, not every KORA product feature.
Arithmetic executes on the controller CPU; use model-only results for a strict
same-model-device comparison. Backend configuration must match the worker.
"""

from __future__ import annotations

import json
import time

from .three_system import deterministic_work
from .worker import ModelBackend, WorkerError, digest


def execute_direct(backend_config, fixture, system_prompt, scenario="M"):
    if scenario not in ("D", "M", "W"):
        raise ValueError("unsupported scenario")
    system_prompt = fixture.get("system_prompt", system_prompt)
    start = time.monotonic()
    result = {
        "schema_version": "kora.benchmark.direct/v1",
        "scenario": scenario,
        "workload_id": fixture["id"],
        "input_hash": digest({"fixture": fixture, "system_prompt": system_prompt}),
        "kora_worker_routing": False,
        "result_reuse": False,
        "configuration": backend_config.get("identity", {}),
        "model_calls_completed": 0,
        "completion_tokens": 0,
        "quality_pass": False,
        "status": "failed",
        "arithmetic_location": "controller-cpu" if scenario != "M" else None,
    }
    try:
        actual, expected = {}, {}
        if scenario in ("D", "W"):
            actual.update(
                deterministic_work(
                    fixture["structured_input"],
                    fixture.get("deterministic_operation", "arithmetic"),
                )
            )
            expected.update(fixture["expected_deterministic_output"])
        if scenario in ("M", "W"):
            backend = ModelBackend(**backend_config)
            backend.health()
            output = backend.generate(
                {"system": system_prompt, "text": fixture["text"]}
            )
            result.update(
                model_calls_completed=1,
                completion_tokens=output["completion_tokens"],
                raw_model_output=output,
            )
            parsed = json.loads(output["text"])
            if not isinstance(parsed, dict) or set(parsed) != (
                {"category", "reply"}
                if fixture.get("model_contract") == "reply-v1"
                else {"category"}
            ):
                raise WorkerError("quality-invalid-model-schema")
            actual.update(parsed)
            expected.update(fixture["expected_model_output"])
        result.update(
            status="completed", output=actual, quality_pass=actual == expected
        )
    except (WorkerError, ValueError, KeyError, TypeError) as exc:
        result["error"] = (
            exc.code if isinstance(exc, WorkerError) else "invalid-output-or-config"
        )
    result["controller_elapsed_ms"] = (time.monotonic() - start) * 1000
    return result
