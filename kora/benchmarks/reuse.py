"""Bounded fixture-node reuse. Host boot, code, data and configuration fence each entry."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path

from .worker import digest, encoded


class ExactReuse:
    def __init__(self, root, snapshot, capacity=256):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshot, self.capacity = snapshot, capacity
        self.lock = threading.Lock()
        self.code = digest(
            {
                name: (Path(__file__).parent / name).read_text()
                for name in (
                    "reuse.py",
                    "worker.py",
                    "three_system.py",
                    "reference_workload.py",
                )
            }
        )

    def key(self, system, config, fixture, prompt, operation, value, health):
        if system == "h100" or operation not in ("arithmetic", "clean-orders", "model"):
            return None
        if health.get("model_fault"):
            return None
        identity = health.get("operation_identity", {}).get(operation)
        if operation == "model" and not identity:
            return None  # Legacy workers cannot attest their configured generation settings.
        return digest(
            {
                "version": 1,
                "system": system,
                "config": config,
                "fixture": fixture,
                "prompt": prompt,
                "operation": operation,
                "value": value,
                "boot_id": health["boot_id"],
                "worker_id": health["worker_id"],
                "backend": identity,
                "code": self.code,
                "snapshot": self.snapshot,
            }
        )

    def get(self, key, job_id):
        import time

        start = time.monotonic()
        with self.lock:
            try:
                raw = (self.root / (key + ".json")).read_bytes()
                if len(raw) > 131072:
                    return None
                entry = json.loads(raw)
                node = entry["node"]
                if entry["key"] != key or entry["checksum"] != digest(node):
                    return None
                if (
                    node["status"] != "completed"
                    or node.get("activity") == "exact-reuse"
                ):
                    return None
            except (OSError, ValueError, KeyError, TypeError):
                return None
        result = copy.deepcopy(node)
        result.update(
            source_job_id=node["job_id"],
            job_id=job_id,
            source_activity=node["activity"],
            activity="exact-reuse",
            model_calls_completed=0,
            duplicate_delivery=False,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
        return result

    def put(self, key, node):
        if node.get("status") != "completed" or node.get("activity") == "exact-reuse":
            return
        with self.lock:
            if len(list(self.root.glob("*.json"))) >= self.capacity:
                return  # Bounded, never evict another running experiment's evidence.
            body = encoded({"key": key, "node": node, "checksum": digest(node)})
            fd, name = tempfile.mkstemp(dir=self.root, prefix=".pending-")
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(body)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(name, self.root / (key + ".json"))
            finally:
                if os.path.exists(name):
                    os.unlink(name)
