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
        del budget, output_schema
        question = str(input.get("question", ""))
        return {
            "ok": True,
            "output": {
                "status": "ok",
                "task_id": task_id,
                "answer": f"Mock answer for: {question[:80]}",
            },
            "usage": {
                "time_ms": 25,
                "tokens_in": max(1, len(question) // 4),
                "tokens_out": 40,
            },
            "meta": {"adapter": "mock", "model": "mock-v0"},
        }
