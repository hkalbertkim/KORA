import copy
import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from kora.benchmarks import three_system
from kora.benchmarks.dashboard import Comparison, make_server
from kora.benchmarks.reuse import ExactReuse
from kora.benchmarks.worker import digest

FIXTURES = json.loads(
    Path("examples/benchmarks/three-environment/workloads.json").read_text()
)
CONFIG = json.loads(
    Path("examples/benchmarks/three-environment/systems.example.json").read_text()
)


class FakeClient:
    calls = []  # noqa: RUF012 - intentional shared test call ledger
    boot = "boot-1"
    category = "billing"

    def __init__(self, **kw):
        self.worker_id = kw["worker_id"]
        self.health = {
            "boot_id": self.boot,
            "worker_id": self.worker_id,
            "operation_identity": {"model": {"generation": {"seed": 42}}},
        }

    def run(self, job_id, operation, value):
        self.calls.append(operation)
        output = (
            three_system.arithmetic(value)
            if operation == "arithmetic"
            else {
                "text": json.dumps({"category": self.category}),
                "completion_tokens": 10,
            }
        )
        return {
            "worker_id": self.worker_id,
            "job_id": job_id,
            "activity": operation,
            "status": "completed",
            "output": output,
            "elapsed_ms": 1,
            "model_calls_completed": int(operation == "model"),
        }


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("KORA_BENCHMARK_TOKEN", "x" * 32)
    monkeypatch.setattr(three_system, "Client", FakeClient)
    FakeClient.calls, FakeClient.boot, FakeClient.category = [], "boot-1", "billing"


def run(cache, config=None, fixture=None, system="cluster"):
    return three_system.execute_case(
        system,
        config or CONFIG[system],
        fixture or FIXTURES["cases"][0],
        FIXTURES["system_prompt"],
        "W",
        str(time.time_ns()),
        lambda event: None,
        cache,
    )


def test_reuse_has_zero_new_model_activity_and_no_live_cooperation(tmp_path, fake):
    cache = ExactReuse(tmp_path, digest(FIXTURES))
    first, second = run(cache), run(cache)
    assert first["quality_pass"] and second["quality_pass"]
    assert first["cluster_cooperation_observed"]
    assert second["reused_nodes"] == 2
    assert second["model_calls_completed"] == second["completion_tokens"] == 0
    assert not second["cluster_cooperation_observed"]
    assert FakeClient.calls == ["arithmetic", "model"]


@pytest.mark.parametrize("change", ["input", "config", "boot", "snapshot", "code"])
def test_identity_changes_invalidate(tmp_path, fake, change):
    cache = ExactReuse(tmp_path, digest(FIXTURES))
    run(cache)
    config, fixture = (
        copy.deepcopy(CONFIG["cluster"]),
        copy.deepcopy(FIXTURES["cases"][0]),
    )
    if change == "input":
        fixture["text"] += " "
    if change == "config":
        config["identity"]["quantization"] = "changed"
    if change == "boot":
        FakeClient.boot = "boot-2"
    if change == "snapshot":
        cache.snapshot = "changed"
    if change == "code":
        cache.code = "changed"
    assert run(cache, config, fixture)["reused_nodes"] == 0


def test_bad_quality_not_cached_and_corruption_is_miss(tmp_path, fake):
    cache = ExactReuse(tmp_path, digest(FIXTURES))
    FakeClient.category = "wrong"
    assert not run(cache)["quality_pass"]
    assert not list(tmp_path.glob("*.json"))
    FakeClient.category = "billing"
    run(cache)
    for path in tmp_path.glob("*.json"):
        path.write_text('{"bad":true}')
    assert run(cache)["reused_nodes"] == 0


def test_native_never_reuses(tmp_path):
    assert (
        ExactReuse(tmp_path, "snapshot").key("h100", {}, {}, "", "model", {}, {})
        is None
    )


def test_http_origin_validation_and_durable_results(tmp_path, fake):
    app = Comparison(CONFIG, FIXTURES, tmp_path)
    server = make_server(app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = json.dumps(
        {
            "case": "billing-en",
            "scenario": "D",
            "reuse": True,
            "changed": False,
            "repetitions": 1,
        }
    ).encode()
    try:
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(base + "/api/runs", data=payload))
        assert exc.value.code == 403
        with pytest.raises(HTTPError):
            urlopen(Request(base + "/api/meta", headers={"Host": "evil.invalid"}))
        with urlopen(
            Request(
                base + "/api/runs", data=payload, headers={"X-Kora-Token": app.token}
            )
        ) as response:
            run_id = json.load(response)["id"]
        for _ in range(100):
            state = app.get(run_id)
            if state["status"] != "running":
                break
            time.sleep(0.02)
        assert state["status"] == "completed"
        assert len(state["results"]) == 3
        assert all(r["model_calls_completed"] == 0 for r in state["results"])
        recorded = Comparison(CONFIG, FIXTURES, tmp_path).get(run_id)
        assert recorded["source"] == "recorded"
        assert len((tmp_path / run_id / "results.jsonl").read_text().splitlines()) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_guard_blocks_before_inference(tmp_path, fake):
    app = Comparison(CONFIG, FIXTURES, tmp_path)
    rid = app.submit(
        {
            "case": "billing-en",
            "scenario": "M",
            "reuse": True,
            "changed": False,
            "repetitions": 2,
        }
    )["id"]
    for _ in range(100):
        state = app.get(rid)
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["status"] == "completed-with-failures"
    assert sum(r["status"] == "blocked" for r in state["results"]) == 2
    assert all(r["reused_nodes"] == 0 for r in state["results"])
    assert FakeClient.calls == ["model"] * 4


def test_native_guard_rejects_stale_foreign_and_expired_leases():
    from datetime import datetime, timedelta, timezone

    from kora.benchmarks.native_guard import validate_status
    from kora.benchmarks.worker import WorkerError

    now = datetime.now(timezone.utc)
    status = {
        "lease": {
            "lease_id": "lease",
            "project": "project",
            "unit": "bench.service",
            "expected_end": (now + timedelta(minutes=5)).isoformat(),
        },
        "overdue": False,
        "observed": {
            "sampled_at": now.isoformat(),
            "processes": [{"service": "bench.service"}],
        },
    }
    assert (
        validate_status(status, "lease", "project", "bench.service", now)["lease_id"]
        == "lease"
    )
    for change in ("stale", "foreign", "expired", "missing", "wrong-id"):
        value = copy.deepcopy(status)
        if change == "stale":
            value["observed"]["sampled_at"] = (now - timedelta(seconds=31)).isoformat()
        if change == "foreign":
            value["observed"]["processes"][0]["service"] = "other.service"
        if change == "expired":
            value["lease"]["expected_end"] = now.isoformat()
        if change == "missing":
            value["lease"] = None
        if change == "wrong-id":
            value["lease"]["lease_id"] = "other"
        with pytest.raises(WorkerError):
            validate_status(value, "lease", "project", "bench.service", now)


def test_changed_input_does_not_generate_oracle_with_tested_function(
    tmp_path, fake, monkeypatch
):
    monkeypatch.setattr(
        three_system, "arithmetic", lambda value: {"total": 0, "currency": "KRW"}
    )
    app = Comparison(CONFIG, FIXTURES, tmp_path)
    rid = app.submit(
        {
            "case": "billing-en",
            "scenario": "D",
            "reuse": False,
            "changed": True,
            "repetitions": 1,
        }
    )["id"]
    for _ in range(100):
        state = app.get(rid)
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert len(state["results"]) == 3
    assert all(
        r["status"] == "completed" and not r["quality_pass"] for r in state["results"]
    )
