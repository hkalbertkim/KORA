"""Base adapter protocol for external reasoning backends."""

from __future__ import annotations

from typing import Any


class BaseAdapter:
    """Minimal adapter interface for v0.1."""

    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
