"""Minimal OpenAI HTTP adapter for structured JSON responses."""

from __future__ import annotations

import copy
import json
import os
import time
from typing import Any

import requests

from .base import BaseAdapter


def harden_schema_for_openai(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied schema hardened for OpenAI structured outputs."""
    hardened = copy.deepcopy(schema)

    if not isinstance(hardened, dict):
        return hardened

    schema_type = hardened.get("type")
    if schema_type == "object":
        if "additionalProperties" not in hardened:
            hardened["additionalProperties"] = False

        properties = hardened.get("properties")
        if isinstance(properties, dict):
            hardened["properties"] = {
                key: harden_schema_for_openai(value)
                for key, value in properties.items()
            }

    if schema_type == "array" and "items" in hardened:
        items = hardened["items"]
        if isinstance(items, dict):
            hardened["items"] = harden_schema_for_openai(items)
        elif isinstance(items, list):
            hardened["items"] = [harden_schema_for_openai(item) for item in items]

    for key in ("anyOf", "oneOf", "allOf"):
        value = hardened.get(key)
        if isinstance(value, list):
            hardened[key] = [harden_schema_for_openai(item) for item in value]

    return hardened


class OpenAIAdapter(BaseAdapter):
    """OpenAI Responses API adapter using requests."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.endpoint = "https://api.openai.com/v1/responses"

    def run(
        self,
        *,
        task_id: str,
        input: dict[str, Any],
        budget: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        start = time.monotonic()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "ok": False,
                "error": "OPENAI_API_KEY is missing",
                "output": {},
                "usage": {"time_ms": 0, "tokens_in": 0, "tokens_out": 0},
                "meta": {"adapter": "openai", "model": self.model},
            }

        timeout_seconds = max(float(budget.get("max_time_ms", 1500)) / 1000.0 + 1.0, 0.1)
        max_tokens = int(budget.get("max_tokens", 300))
        hardened_schema = harden_schema_for_openai(output_schema)

        prompt_payload = {
            "task_id": task_id,
            "input": input,
            "requirements": "Return JSON only. No prose.",
        }
        request_payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are a strict JSON engine. Return only valid JSON.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(prompt_payload)}],
                },
            ],
            "max_output_tokens": max_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "kora_output",
                    "schema": hardened_schema,
                    "strict": True,
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=request_payload,
                timeout=timeout_seconds,
            )
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"OpenAI API error {response.status_code}: {response.text[:240]}",
                    "output": {},
                    "usage": {
                        "time_ms": int((time.monotonic() - start) * 1000),
                        "tokens_in": 0,
                        "tokens_out": 0,
                    },
                    "meta": {"adapter": "openai", "model": self.model},
                }

            payload = response.json()
            text_output = self._extract_text(payload)
            parsed_output = json.loads(text_output)

            usage = payload.get("usage", {})
            return {
                "ok": True,
                "output": parsed_output,
                "usage": {
                    "time_ms": int((time.monotonic() - start) * 1000),
                    "tokens_in": int(usage.get("input_tokens", 0)),
                    "tokens_out": int(usage.get("output_tokens", 0)),
                },
                "meta": {"adapter": "openai", "model": self.model},
            }
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "error": f"OpenAI adapter failed: {exc}",
                "output": {},
                "usage": {
                    "time_ms": int((time.monotonic() - start) * 1000),
                    "tokens_in": 0,
                    "tokens_out": 0,
                },
                "meta": {"adapter": "openai", "model": self.model},
            }

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text

        output_items = payload.get("output", [])
        for item in output_items:
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(
                    content.get("text"), str
                ):
                    return content["text"]

        raise ValueError("OpenAI response did not include textual JSON output")
