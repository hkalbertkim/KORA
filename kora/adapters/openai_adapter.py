"""OpenAI adapter placeholder.

No credentials or API secrets should be stored in source.
"""

from .base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """Placeholder OpenAI-backed adapter."""

    def run(self, task: dict) -> dict:
        raise NotImplementedError("TODO: implement OpenAI adapter")
