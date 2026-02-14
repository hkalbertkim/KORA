"""Mock adapter for local testing (placeholder)."""

from .base import BaseAdapter


class MockAdapter(BaseAdapter):
    """Mock adapter that returns static output."""

    def run(self, task: dict) -> dict:
        return {"status": "ok", "task_id": task.get("id")}
