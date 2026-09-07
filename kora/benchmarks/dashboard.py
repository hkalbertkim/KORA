"""Local fixed-fixture comparison screen. Reach remote hosts through SSH tunnels."""

from __future__ import annotations

import argparse
import copy
import json
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .reuse import ExactReuse
from .three_system import execute_case
from .worker import WorkerError, digest, encoded


class Comparison:
    def __init__(self, config, fixtures, root, h100_guard=None):
        self.config, self.fixtures = config, fixtures
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.reuse = ExactReuse(self.root / "cache", digest(fixtures))
        self.h100_guard = h100_guard
        self.lock, self.busy = threading.Lock(), False
        self.runs = {}
        self.token = secrets.token_hex(32)

    def metadata(self):
        history = []
        for path in sorted(
            self.root.glob("*/state.json"), key=lambda p: p.stat().st_mtime
        )[-50:]:
            try:
                saved = json.loads(path.read_text())
                history.append(
                    {
                        "id": saved["id"],
                        "started_at": saved["started_at"],
                        "scenario": saved["request"]["scenario"],
                        "status": saved["status"],
                    }
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return {
            "cases": [
                {
                    "id": c["id"],
                    "text": c["text"],
                    "structured_input": c["structured_input"],
                }
                for c in self.fixtures["cases"]
            ],
            "native_enabled": self.h100_guard is not None,
            "configuration": {
                k: v.get("identity", {})
                for k, v in self.config.items()
                if k in ("mp", "cluster", "h100")
            },
            "runs": [item["id"] for item in history],
            "history": history,
        }

    def submit(self, request):
        if not isinstance(request, dict) or set(request) != {
            "case",
            "scenario",
            "reuse",
            "changed",
            "repetitions",
        }:
            raise WorkerError("invalid-request")
        if (
            request["scenario"] not in ("D", "M", "W")
            or type(request["reuse"]) is not bool
            or type(request["changed"]) is not bool
            or type(request["repetitions"]) is not int
            or not 1 <= request["repetitions"] <= 5
        ):
            raise WorkerError("invalid-options")
        cases = [
            c for c in self.fixtures["cases"] if request["case"] in (c["id"], "all")
        ]
        if not cases:
            raise WorkerError("unknown-case")
        with self.lock:
            if self.busy:
                raise WorkerError("comparison-in-progress", 409)
            self.busy = True
            run_id = str(uuid.uuid4())
            state = {
                "id": run_id,
                "status": "running",
                "source": "live",
                "started_at": time.time(),
                "request": request,
                "events": [],
                "results": [],
                "total": len(cases) * 3 * request["repetitions"],
                "snapshot": digest(self.fixtures),
                "timing": "controller-wall-clock",
                "load_condition": "warmth-and-background-load-not-controlled",
                "code_snapshot": {
                    p.name: digest(p.read_text())
                    for p in Path(__file__).parent.glob("*.py")
                },
            }
            try:
                (self.root / run_id).mkdir()
                self.runs[run_id] = state
                self.save(state)
                threading.Thread(
                    target=self.run, args=(state, cases), daemon=True
                ).start()
            except Exception:
                self.busy = False
                raise
        return {"id": run_id}

    def save(self, state):
        folder = self.root / state["id"]
        tmp = folder / "state.pending"
        tmp.write_bytes(encoded(state))
        tmp.replace(folder / "state.json")

    def get(self, run_id):
        try:
            if str(uuid.UUID(run_id)) != run_id:
                raise ValueError()
        except ValueError as exc:
            raise WorkerError("invalid-run-id") from exc
        with self.lock:
            if run_id in self.runs:
                return copy.deepcopy(self.runs[run_id])
            try:
                state = json.loads((self.root / run_id / "state.json").read_text())
            except (OSError, ValueError) as exc:
                raise WorkerError("run-not-found", 404) from exc
        state["source"] = "recorded"
        if state["status"] == "running":
            state["status"] = "interrupted"
        return state

    def run(self, state, cases):
        folder, options = self.root / state["id"], state["request"]
        try:
            with (
                (folder / "events.jsonl").open("a") as event_log,
                (folder / "results.jsonl").open("a") as result_log,
            ):

                def emit(event):
                    event_log.write(json.dumps(event, ensure_ascii=False) + "\n")
                    event_log.flush()
                    with self.lock:
                        state["events"].append(event)
                        state["events"] = state["events"][-200:]
                        self.save(state)

                for repetition in range(options["repetitions"]):
                    for original in cases:
                        fixture = copy.deepcopy(original)
                        if options["changed"]:
                            structured = fixture["structured_input"]
                            expected = fixture["expected_deterministic_output"]
                            # Update the fixed oracle, never call the implementation
                            # under test to manufacture its own expected result.
                            if fixture.get("deterministic_operation") == "clean-orders":
                                structured["rows"][0]["quantity"] += 1
                                expected["orders"][0]["quantity"] += 1
                                increment = expected["orders"][0]["unit_price"]
                                expected["orders"][0]["total"] += increment
                            else:
                                structured["quantity"] += 1
                                increment = structured["unit_price"]
                            expected["total"] += increment
                            index = self.fixtures["cases"].index(original)
                            next_case = self.fixtures["cases"][
                                (index + 1) % len(self.fixtures["cases"])
                            ]
                            for key in ("system_prompt", "model_contract"):
                                fixture.pop(key, None)
                                if key in next_case:
                                    fixture[key] = next_case[key]
                            fixture["text"] = next_case["text"]
                            fixture["expected_model_output"] = next_case[
                                "expected_model_output"
                            ]
                        for system in ("mp", "cluster", "h100"):
                            run_id = str(uuid.uuid4())
                            try:
                                if system == "h100" and options["scenario"] != "D":
                                    if self.h100_guard is None:
                                        raise WorkerError(
                                            "h100-window-not-enabled", 409
                                        )
                                    self.h100_guard()
                                result = execute_case(
                                    system,
                                    self.config[system],
                                    fixture,
                                    self.fixtures["system_prompt"],
                                    options["scenario"],
                                    run_id,
                                    emit,
                                    self.reuse
                                    if options["reuse"] and options["scenario"] != "M"
                                    else None,
                                )
                            except WorkerError as exc:
                                result = {
                                    "run_id": run_id,
                                    "system_set": system,
                                    "workload_id": fixture["id"],
                                    "scenario": options["scenario"],
                                    "status": "blocked",
                                    "error": exc.code,
                                    "quality_pass": False,
                                    "nodes": [],
                                    "model_calls_completed": 0,
                                    "completion_tokens": 0,
                                    "reused_nodes": 0,
                                    "controller_elapsed_ms": None,
                                }
                                emit(
                                    {
                                        "system_set": system,
                                        "run_id": run_id,
                                        "event_kind": "blocked",
                                        "error": exc.code,
                                    }
                                )
                            result["repetition"] = repetition
                            result["input_variant"] = (
                                "changed" if options["changed"] else "original"
                            )
                            result_log.write(
                                json.dumps(result, ensure_ascii=False) + "\n"
                            )
                            result_log.flush()
                            with self.lock:
                                state["results"].append(result)
                                self.save(state)
            with self.lock:
                state["status"] = (
                    "completed"
                    if all(r["quality_pass"] for r in state["results"])
                    else "completed-with-failures"
                )
        except Exception:  # noqa: BLE001 - preserve controller failures as terminal evidence
            with self.lock:
                state["status"] = "interrupted"
                state["error"] = "controller-failure-see-local-logs"
        finally:
            with self.lock:
                state["ended_at"] = time.time()
                self.busy = False
                self.save(state)
                # Bound resident history; durable results remain addressable on disk.
                for key in list(self.runs)[:-10]:
                    del self.runs[key]


def make_server(app, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, value, content_type="application/json"):
            body = value if isinstance(value, bytes) else encoded(value)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def safe_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.safe_host():
                return self.respond(403, {"error": "loopback-host-required"})
            path = urlsplit(self.path).path
            try:
                if path in ("/", "/app.js", "/style.css"):
                    name = {
                        "/": "index.html",
                        "/app.js": "app.js",
                        "/style.css": "style.css",
                    }[path]
                    mime = {
                        "/": "text/html; charset=utf-8",
                        "/app.js": "text/javascript; charset=utf-8",
                        "/style.css": "text/css",
                    }[path]
                    return self.respond(
                        200,
                        (Path(__file__).parent / "assets" / name).read_bytes(),
                        mime,
                    )
                if path == "/api/meta":
                    return self.respond(200, {**app.metadata(), "csrf": app.token})
                if path.startswith("/api/runs/"):
                    return self.respond(200, app.get(path.removeprefix("/api/runs/")))
                return self.respond(404, {"error": "not-found"})
            except WorkerError as exc:
                self.respond(exc.status, {"error": exc.code})

        def do_POST(self):
            self.connection.settimeout(5)
            if (
                not self.safe_host()
                or self.headers.get("X-Kora-Token") != app.token
                or self.headers.get("Origin")
                not in (None, f"http://127.0.0.1:{self.server.server_port}")
            ):
                return self.respond(403, {"error": "unauthorized-origin-or-token"})
            if self.path != "/api/runs":
                return self.respond(404, {"error": "not-found"})
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
                    raise WorkerError("invalid-framing")
                length = int(lengths[0])
                if not 0 < length <= 2048:
                    raise WorkerError("request-too-large")
                self.respond(202, app.submit(json.loads(self.rfile.read(length))))
            except WorkerError as exc:
                self.respond(exc.status, {"error": exc.code})
            except (ValueError, TimeoutError):
                self.respond(400, {"error": "invalid-request"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--port", type=int, default=9190)
    parser.add_argument(
        "--native-guard-config",
        help="Private JSON: command argv, lease_id, project, unit",
    )
    args = parser.parse_args()
    app = Comparison(
        json.loads(Path(args.config).read_text()),
        json.loads(Path(args.fixtures).read_text()),
        args.output,
    )
    if args.native_guard_config:
        from .native_guard import NativeGuard

        app.h100_guard = NativeGuard(
            **json.loads(Path(args.native_guard_config).read_text())
        )
        app.h100_guard()  # Fail before serving a UI that advertises an invalid window.
    server = make_server(app, args.port)
    print(f"Comparison screen: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
