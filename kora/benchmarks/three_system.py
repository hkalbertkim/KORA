"""Three-system fixture runner. H100 uses a native endpoint without KORA routing."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

from .worker import VERSION, ModelBackend, WorkerError, digest, http_json


def arithmetic(value):
    if set(value) != {"quantity", "unit_price", "currency"}:
        raise WorkerError("invalid-arithmetic-fields")
    if value["currency"] != "KRW" or any(
        type(value[k]) is not int or not 0 <= value[k] <= 10**9
        for k in ("quantity", "unit_price")
    ):
        raise WorkerError("invalid-arithmetic-value")
    return {"total": value["quantity"] * value["unit_price"], "currency": "KRW"}


def deterministic_work(value, operation="arithmetic"):
    if operation == "arithmetic":
        return arithmetic(value)
    if operation == "clean-orders" and set(value) == {"rows"}:
        from .reference_workload import clean_orders

        return clean_orders(value["rows"])
    raise WorkerError("unsupported-deterministic-operation")


class Client:
    def __init__(self, url, token, worker_id):
        self.url, self.token, self.worker_id = url.rstrip("/"), token, worker_id
        health = http_json(self.url + "/health", token=token, timeout=5)
        if (
            not isinstance(health, dict)
            or health.get("worker_id") != worker_id
            or health.get("schema_version") != VERSION
        ):
            raise WorkerError("worker-identity-mismatch")
        self.boot_id = health["boot_id"]
        self.health = health

    def run(self, job_id, operation, value):
        request = {
            "schema_version": VERSION,
            "boot_id": self.boot_id,
            "job_id": job_id,
            "operation": operation,
            "input": value,
            "input_hash": digest(value),
        }
        result = http_json(self.url + "/jobs", request, self.token, timeout=130)
        if not isinstance(result, dict) or any(
            result.get(k) != v
            for k, v in {
                "schema_version": VERSION,
                "worker_id": self.worker_id,
                "boot_id": self.boot_id,
                "job_id": job_id,
                "input_hash": digest(value),
                "operation": operation,
            }.items()
        ):
            raise WorkerError("result-identity-mismatch")
        return result


def execute_case(
    system, config, fixture, system_prompt, scenario, run_id, emit, reuse=None
):
    """Every outcome, including failed/unsupported runs, remains in the denominator."""
    system_prompt = fixture.get("system_prompt", system_prompt)
    payload = {
        "text": fixture["text"],
        "structured_input": fixture["structured_input"],
        "system_prompt": system_prompt,
    }
    result = {
        "schema_version": "kora.benchmark.execution/v1",
        "run_id": run_id,
        "system_set": system,
        "workload_id": fixture["id"],
        "scenario": scenario,
        "input_hash": digest(payload),
        "status": "failed",
        "quality_pass": False,
        "nodes": [],
        "configuration": config.get("identity", {}),
        "model_calls_completed": 0,
        "completion_tokens": 0,
        "execution_location": "native-client-only"
        if system == "h100" and scenario == "D"
        else "native-client-and-endpoint"
        if system == "h100"
        else "kora-workers",
    }
    operation_name = fixture.get("deterministic_operation", "arithmetic")
    pending_cache = []
    started = time.monotonic()
    sequence = 0

    def event(kind, **fields):
        nonlocal sequence
        sequence += 1
        emit(
            {
                "schema_version": "kora.benchmark.event/v1",
                "run_id": run_id,
                "system_set": system,
                "sequence": sequence,
                "event_kind": kind,
                "controller_elapsed_ms": (time.monotonic() - started) * 1000,
                **fields,
            }
        )

    event("started")
    try:
        if system == "h100":
            # Fail before work on a mismatched model, even for the mixed baseline.
            if scenario != "D":
                backend = ModelBackend(**config["backend"])
                backend.health()
            deterministic = None
            if scenario in ("D", "W"):
                node_start = time.monotonic()
                deterministic = deterministic_work(
                    fixture["structured_input"], operation_name
                )
                node = {
                    "worker_id": "native-client",
                    "activity": "deterministic",
                    "status": "completed",
                    "model_calls_completed": 0,
                    "elapsed_ms": (time.monotonic() - node_start) * 1000,
                    "output": deterministic,
                }
                result["nodes"].append(node)
                event("node-completed", node=node)
            model = None
            if scenario in ("M", "W"):
                event("node-started", node_id="model", activity="inference")
                node_start = time.monotonic()
                model = backend.generate(
                    {"system": system_prompt, "text": fixture["text"]}
                )
                node = {
                    "worker_id": "native-h100-endpoint",
                    "activity": "inference",
                    "status": "completed",
                    "model_calls_completed": 1,
                    "output": model,
                    "elapsed_ms": (time.monotonic() - node_start) * 1000,
                }
                result["nodes"].append(node)
                event("node-completed", node=node)
        else:
            token = os.environ[config["token_env"]]
            model_cfg = config["model_worker"]
            deterministic_cfg = config["deterministic_worker"]
            if (
                system == "cluster"
                and model_cfg["worker_id"] == deterministic_cfg["worker_id"]
            ):
                raise WorkerError("cluster-requires-distinct-workers")
            deterministic = model = None
            for operation, value, worker_cfg in [
                (operation_name, fixture["structured_input"], deterministic_cfg),
                (
                    "model",
                    {"system": system_prompt, "text": fixture["text"]},
                    model_cfg,
                ),
            ]:
                if (scenario == "D" and operation == "model") or (
                    scenario == "M" and operation != "model"
                ):
                    continue
                client = Client(token=token, **worker_cfg)
                event("node-started", node_id=operation, worker_id=client.worker_id)
                cache_key = None
                if reuse is not None:
                    cache_key = reuse.key(
                        system,
                        config,
                        fixture,
                        system_prompt,
                        operation,
                        value,
                        client.health,
                    )
                node = (
                    reuse.get(cache_key, run_id + ":" + operation)
                    if cache_key
                    else None
                )
                if node is None:
                    node = client.run(run_id + ":" + operation, operation, value)
                    if cache_key and node.get("status") == "completed":
                        pending_cache.append((cache_key, node))
                else:
                    event(
                        "node-reused",
                        node_id=operation,
                        source_job_id=node["source_job_id"],
                    )
                result["nodes"].append(node)
                event(
                    "node-completed"
                    if node["status"] == "completed"
                    else "node-failed",
                    node=node,
                )
                if node["status"] != "completed":
                    raise WorkerError(node.get("error", "worker-failed"), 502)
                if operation != "model":
                    deterministic = node["output"]
                else:
                    model = node["output"]
        actual = dict(deterministic or {})
        if model:
            parsed = json.loads(model["text"])
            if not isinstance(parsed, dict) or set(parsed) != (
                {"category", "reply"}
                if fixture.get("model_contract") == "reply-v1"
                else {"category"}
            ):
                raise WorkerError("quality-invalid-model-schema")
            actual.update(parsed)
        expected = {}
        if scenario in ("D", "W"):
            expected.update(fixture["expected_deterministic_output"])
        if scenario in ("M", "W"):
            expected.update(fixture["expected_model_output"])
        result.update(
            status="completed", output=actual, quality_pass=actual == expected
        )
    except (WorkerError, ValueError, KeyError, TypeError) as exc:
        result["error"] = (
            exc.code if isinstance(exc, WorkerError) else "invalid-output-or-config"
        )
        event("failed", error=result["error"])
    if result["quality_pass"] and reuse is not None:
        for key, node in pending_cache:
            reuse.put(key, node)
    result["reused_nodes"] = sum(
        n.get("activity") == "exact-reuse" for n in result["nodes"]
    )
    result["model_calls_completed"] = sum(
        n.get("model_calls_completed", 0) for n in result["nodes"]
    )
    result["completion_tokens"] = sum(
        n.get("output", {}).get("completion_tokens", 0)
        for n in result["nodes"]
        if n.get("activity") != "exact-reuse"
    )
    result["controller_elapsed_ms"] = (time.monotonic() - started) * 1000
    result["cluster_cooperation_observed"] = (
        system == "cluster"
        and scenario == "W"
        and len(
            {
                n["worker_id"]
                for n in result["nodes"]
                if n["status"] == "completed" and n.get("activity") != "exact-reuse"
            }
        )
        == 2
    )
    event("finished", status=result["status"], quality_pass=result["quality_pass"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--scenario", choices=["D", "M", "W"], default="W")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--case", default=None)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 20:
        parser.error("repetitions must be 1..20")
    config = json.loads(Path(args.config).read_text())
    fixtures = json.loads(Path(args.fixtures).read_text())
    if args.case and args.case not in [case["id"] for case in fixtures["cases"]]:
        parser.error("unknown fixture case")
    failed = False
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    with (
        (output / "events.jsonl").open("x") as events,
        (output / "results.jsonl").open("x") as results,
    ):

        def emit(event):
            events.write(json.dumps(event, ensure_ascii=False) + "\n")
            events.flush()

        print(
            "system\tworkload\tstatus\tquality\telapsed_ms\tactual_output_tokens",
            flush=True,
        )
        for repetition in range(args.repetitions):
            for fixture in fixtures["cases"]:
                if args.case and fixture["id"] != args.case:
                    continue
                for system in ("mp", "cluster", "h100"):
                    result = execute_case(
                        system,
                        config[system],
                        fixture,
                        fixtures["system_prompt"],
                        args.scenario,
                        str(uuid.uuid4()),
                        emit,
                    )
                    failed = failed or not result["quality_pass"]
                    result["repetition"] = repetition
                    results.write(json.dumps(result, ensure_ascii=False) + "\n")
                    results.flush()
                    label = (
                        "h100-client-only"
                        if system == "h100" and args.scenario == "D"
                        else system
                    )
                    print(
                        f"{label}\t{fixture['id']}\t{result['status']}\t{result['quality_pass']}\t"
                        f"{result['controller_elapsed_ms']:.1f}\t{result['completion_tokens']}",
                        flush=True,
                    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
