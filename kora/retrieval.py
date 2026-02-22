"""Minimal deterministic in-process retrieval store."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class InMemoryRetrievalStore:
    """Simple key-value retrieval store for deterministic lookups."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        self._items[key] = value

    def get(self, key: str) -> Any | None:
        return self._items.get(key)

    def clear(self) -> None:
        self._items.clear()


def build_retrieval_key(
    task_type: str,
    input_payload: dict[str, Any],
    tags: list[str] | None = None,
) -> str:
    """Build a deterministic retrieval key from task shape and input payload."""
    payload: dict[str, Any] = {
        "task_type": task_type,
        "input_payload": input_payload,
    }
    if tags:
        payload["tags"] = list(tags)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
