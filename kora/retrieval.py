"""Minimal deterministic in-process retrieval store."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _Entry:
    value: Any
    expire_at: float | None


class InMemoryRetrievalStore:
    """Simple key-value retrieval store with TTL and bounded LRU eviction."""

    def __init__(
        self,
        *,
        max_entries: int = 1000,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._items: OrderedDict[str, _Entry] = OrderedDict()
        self._max_entries = max(1, int(max_entries))
        self._clock = clock or time.time

    def configure(self, *, max_entries: int | None = None) -> None:
        if max_entries is not None:
            self._max_entries = max(1, int(max_entries))
            self._evict_over_limit()

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expire_at: float | None = None
        if ttl_seconds is not None:
            ttl = int(ttl_seconds)
            if ttl <= 0:
                self._items.pop(key, None)
                return
            expire_at = float(self._clock()) + float(ttl)
        self._items[key] = _Entry(value=value, expire_at=expire_at)
        self._items.move_to_end(key)
        self._evict_over_limit()

    def get(self, key: str) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expire_at is not None and float(self._clock()) >= entry.expire_at:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return entry.value

    def clear(self) -> None:
        self._items.clear()

    def _evict_over_limit(self) -> None:
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)


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
