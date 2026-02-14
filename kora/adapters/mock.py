"""Mock adapter for local testing (placeholder)."""

from __future__ import annotations

from typing import Any

from .base import BaseAdapter


class MockAdapter(BaseAdapter):
    """Mock adapter that returns static output."""

    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        del input, budget, output_schema
        return {
            "ok": True,
            "output": {"status": "ok", "task_id": task_id},
            "usage": {"time_ms": 0, "tokens_in": 0, "tokens_out": 0},
            "meta": {"adapter": "mock", "model": "mock-v0"},
        }
