import json
import threading
from pathlib import Path

from kora.benchmarks.reuse import ExactReuse
from kora.benchmarks.three_system import deterministic_work, execute_case
from kora.benchmarks.worker import Worker, make_server


def test_order_fixture_through_http_and_reuse(tmp_path, monkeypatch):
    fixture = json.loads(
        Path("examples/benchmarks/three-environment/order-workloads.json").read_text()
    )["cases"][0]
    token = "x" * 32
    monkeypatch.setenv("ORDER_TEST_TOKEN", token)
    worker = Worker(
        "orders",
        token,
        {"clean-orders": lambda value: deterministic_work(value, "clean-orders")},
    )
    server = make_server(worker, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = {"url": f"http://127.0.0.1:{server.server_port}", "worker_id": "orders"}
    config = {
        "token_env": "ORDER_TEST_TOKEN",
        "model_worker": endpoint,
        "deterministic_worker": endpoint,
    }
    cache = ExactReuse(tmp_path, "orders-v1")
    try:
        first = execute_case(
            "mp", config, fixture, "", "D", "first", lambda e: None, cache
        )
        second = execute_case(
            "mp", config, fixture, "", "D", "second", lambda e: None, cache
        )
        assert first["quality_pass"] and second["quality_pass"]
        assert first["nodes"][0]["operation"] == "clean-orders"
        assert second["reused_nodes"] == 1
        assert second["model_calls_completed"] == 0
        fixture["structured_input"]["rows"][0]["quantity"] += 1
        fixture["expected_deterministic_output"]["orders"][0]["quantity"] = 3
        fixture["expected_deterministic_output"]["orders"][0]["total"] = 4500
        fixture["expected_deterministic_output"]["total"] = 10500
        changed = execute_case(
            "mp", config, fixture, "", "D", "changed", lambda e: None, cache
        )
        assert changed["quality_pass"] and changed["reused_nodes"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
