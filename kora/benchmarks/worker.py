"""Bounded benchmark worker, loopback-only. Remote access requires an SSH tunnel.

This harness does not register a network runtime with the offline Solution Host.
The in-memory request ledger is deliberately not an exact-reuse cache: only the
same job ID can retrieve its original outcome. A new ID always executes again.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

LIMIT = 65536
VERSION = "kora.benchmark.worker/v1"


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


class WorkerError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise WorkerError("redirect-refused", 502)


def http_json(url, payload=None, token=None, timeout=120):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username:
        raise WorkerError("loopback-or-ssh-tunnel-required")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        url, data=None if payload is None else encoded(payload), headers=headers
    )
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(
            request, timeout=timeout
        ) as response:
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise WorkerError("response-too-large", 502)
        return json.loads(raw)
    except HTTPError as exc:
        raise WorkerError("http-" + str(exc.code), 502) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise WorkerError("transport-outcome-unknown", 504) from exc
    except (ValueError, UnicodeError) as exc:
        raise WorkerError("invalid-backend-json", 502) from exc


class ModelBackend:
    """Fixed endpoint and model; a model alias alone is not artifact attestation."""

    def __init__(
        self, url, model, generation, identity, timeout=120, token=None, token_env=None
    ):
        self.url, self.model = url.rstrip("/"), model
        self.generation, self.identity = generation, identity
        self.timeout, self.token = (
            timeout,
            os.environ[token_env] if token_env else token,
        )

    def health(self):
        result = http_json(self.url + "/v1/models", token=self.token, timeout=5)
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("data"), list)
            or any(not isinstance(entry, dict) for entry in result["data"])
        ):
            raise WorkerError("invalid-model-list", 502)
        if self.model not in [entry.get("id") for entry in result["data"]]:
            raise WorkerError("model-mismatch", 409)
        return {
            "model": self.model,
            "identity": self.identity,
            "identity_source": "operator-config-plus-served-model-id",
        }

    def generate(self, payload):
        if set(payload) != {"system", "text"} or any(
            not isinstance(v, str) or len(v) > 8192 for v in payload.values()
        ):
            raise WorkerError("invalid-model-input")
        self.health()
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": payload["system"]},
                {"role": "user", "content": payload["text"]},
            ],
            "stream": False,
            **self.generation,
        }
        result = http_json(
            self.url + "/v1/chat/completions", request, self.token, self.timeout
        )
        if not isinstance(result, dict) or not isinstance(result.get("usage"), dict):
            raise WorkerError("missing-engine-token-counts", 502)
        usage = result["usage"]
        if any(
            type(usage.get(k)) is not int or usage[k] < 0
            for k in ("prompt_tokens", "completion_tokens")
        ):
            raise WorkerError("missing-engine-token-counts", 502)
        try:
            choice = result["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise TypeError()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WorkerError("invalid-completion", 502) from exc
        return {
            "text": content,
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "token_source": "engine-reported",
            "backend": {**self.identity, "generation": self.generation},
        }


class Worker:
    def __init__(
        self, worker_id, token, operations, capacity=1024, operation_identity=None
    ):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("worker token must have at least 32 characters")
        self.worker_id, self.token, self.operations = worker_id, token, operations
        self.boot_id, self.started = str(uuid.uuid4()), time.monotonic()
        self.capacity, self.jobs = capacity, {}
        self.operation_identity = operation_identity or {}
        self.model_fault = False
        self.lock = threading.Lock()

    def health(self):
        return {
            "schema_version": VERSION,
            "worker_id": self.worker_id,
            "boot_id": self.boot_id,
            "uptime_seconds": time.monotonic() - self.started,
            "operations": sorted(self.operations),
            "ledger_capacity": self.capacity,
            "model_fault": self.model_fault,
            "operation_identity": self.operation_identity,
        }

    def execute(self, request):
        required = {
            "schema_version",
            "boot_id",
            "job_id",
            "operation",
            "input",
            "input_hash",
        }
        if not isinstance(request, dict) or set(request) != required:
            raise WorkerError("invalid-request")
        if request["schema_version"] != VERSION or request["boot_id"] != self.boot_id:
            raise WorkerError("worker-incarnation-mismatch", 409)
        job = request["job_id"]
        if not isinstance(job, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", job):
            raise WorkerError("invalid-job-id")
        operation = request["operation"]
        if not isinstance(operation, str) or operation not in self.operations:
            raise WorkerError("unsupported-operation")
        if (
            not isinstance(request["input"], dict)
            or digest(request["input"]) != request["input_hash"]
        ):
            raise WorkerError("input-hash-mismatch")
        fingerprint = digest(request)
        with self.lock:
            old = self.jobs.get(job)
            if old:
                if old[0] != fingerprint:
                    raise WorkerError("job-id-conflict", 409)
                if old[1] is None:
                    raise WorkerError("job-in-progress", 409)
                return {**old[1], "duplicate_delivery": True}
            if operation == "model" and self.model_fault:
                raise WorkerError("model-recovery-required", 503)
            if len(self.jobs) >= self.capacity:
                raise WorkerError("ledger-full", 503)
            if any(item[1] is None for item in self.jobs.values()):
                raise WorkerError("worker-busy", 503)
            self.jobs[job] = (fingerprint, None)
        start = time.monotonic()
        result = {
            "schema_version": VERSION,
            "worker_id": self.worker_id,
            "boot_id": self.boot_id,
            "job_id": job,
            "input_hash": request["input_hash"],
            "operation": operation,
            "duplicate_delivery": False,
            "model_calls_completed": 0,
            "activity": "inference" if operation == "model" else "deterministic",
        }
        try:
            output = self.operations[operation](request["input"])
            result.update(status="completed", output=output)
            result["model_calls_completed"] = int(operation == "model")
        except WorkerError as exc:
            result.update(status="failed", error=exc.code)
            if operation == "model":
                result["model_execution_outcome"] = "unknown-or-not-started"
        except Exception:  # noqa: BLE001 - retain a terminal outcome for trusted operation faults
            result.update(status="failed", error="operation-failed")
            if operation == "model":
                result["model_execution_outcome"] = "unknown-or-not-started"
        result["elapsed_ms"] = (time.monotonic() - start) * 1000
        with self.lock:
            if operation == "model" and result["status"] == "failed":
                self.model_fault = True
            self.jobs[job] = (fingerprint, result)
        return result


def make_server(worker, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, value):
            body = encoded(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            supplied = self.headers.get("Authorization", "")
            return hmac.compare_digest(
                supplied.encode(), ("Bearer " + worker.token).encode()
            )

        def do_GET(self):
            if not self.authorized():
                return self.respond(401, {"error": "unauthorized"})
            if self.path != "/health":
                return self.respond(404, {"error": "not-found"})
            self.respond(200, worker.health())

        def do_POST(self):
            self.connection.settimeout(5)
            if not self.authorized():
                return self.respond(401, {"error": "unauthorized"})
            if self.path != "/jobs":
                return self.respond(404, {"error": "not-found"})
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
                    raise WorkerError("invalid-framing")
                length = int(lengths[0])
                if not 0 < length <= LIMIT:
                    raise WorkerError("request-too-large", 413)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise WorkerError("incomplete-request")
                request = json.loads(
                    raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
                )
                self.respond(200, worker.execute(request))
            except WorkerError as exc:
                self.respond(exc.status, {"error": exc.code})
            except (ValueError, UnicodeError, TimeoutError):
                self.respond(400, {"error": "invalid-json-or-framing"})

    class BoundedServer(ThreadingHTTPServer):
        slots = threading.BoundedSemaphore(8)

        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                request.settimeout(5)
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

    server = BoundedServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    with open(args.config) as handle:
        config = json.load(handle)
    token = os.environ["KORA_BENCHMARK_TOKEN"]
    # Fixture logic remains in the benchmark package, never in Core.
    from .three_system import arithmetic, deterministic_work

    operations = {
        "arithmetic": arithmetic,
        "clean-orders": lambda value: deterministic_work(value, "clean-orders"),
    }
    if config.get("backend"):
        operations["model"] = ModelBackend(**config["backend"]).generate
    identity = {}
    if config.get("backend"):
        backend = config["backend"]
        identity["model"] = {
            "model": backend["model"],
            "identity": backend["identity"],
            "generation": backend["generation"],
        }
    worker = Worker(config["worker_id"], token, operations, operation_identity=identity)
    server = make_server(worker, config["port"])
    print(json.dumps(worker.health()), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
