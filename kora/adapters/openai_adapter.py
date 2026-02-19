"""Minimal OpenAI HTTP adapter for structured JSON responses."""

from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
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

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        force_json_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        env_model = os.getenv("KORA_OPENAI_MODEL", "").strip()
        self.model = env_model or model
        self.force_json_schema = force_json_schema
        self.max_output_tokens = max_output_tokens
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

        timeout_env = os.getenv("OPENAI_HTTP_TIMEOUT_SECONDS", "").strip()
        try:
            env_timeout_seconds = float(timeout_env) if timeout_env else 30.0
        except ValueError:
            env_timeout_seconds = 30.0
        timeout_seconds = max(
            float(budget.get("max_time_ms", 1500)) / 1000.0 + 1.0,
            env_timeout_seconds,
            0.1,
        )
        max_tokens = int(budget.get("max_tokens", 300))
        effective_schema = self.force_json_schema if self.force_json_schema is not None else output_schema
        hardened_schema = harden_schema_for_openai(effective_schema)

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
        }
        if self.max_output_tokens is not None:
            request_payload["max_output_tokens"] = int(self.max_output_tokens)
        if self.force_json_schema is not None:
            request_payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "kora_mini",
                    "schema": hardened_schema,
                    "strict": True,
                }
            }
        else:
            request_payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "kora_output",
                    "schema": hardened_schema,
                    "strict": True,
                }
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
            if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                output_items = payload.get("output", [])
                snapshot: dict[str, Any] = {
                    "top_keys": sorted(payload.keys()),
                    "has_output": isinstance(output_items, list),
                    "output_len": len(output_items) if isinstance(output_items, list) else 0,
                    "output_item_types": [],
                    "content_block_types": [],
                    "has_output_text": "output_text" in payload,
                    "output_text_type": type(payload.get("output_text")).__name__ if "output_text" in payload else "None",
                    "has_response_nested": isinstance(payload.get("response"), dict),
                    "nested_keys": sorted(payload.get("response", {}).keys()) if isinstance(payload.get("response"), dict) else [],
                }
                if isinstance(output_items, list):
                    text_head = ""
                    for item in output_items[:5]:
                        if isinstance(item, dict):
                            snapshot["output_item_types"].append(str(item.get("type")))
                        else:
                            snapshot["output_item_types"].append(type(item).__name__)

                    first_two_block_types: list[list[str]] = []
                    for item in output_items[:2]:
                        block_types: list[str] = []
                        if isinstance(item, dict) and isinstance(item.get("content"), list):
                            for block in item["content"]:
                                if isinstance(block, dict):
                                    block_types.append(str(block.get("type")))
                        first_two_block_types.append(block_types)
                    snapshot["content_block_types"] = first_two_block_types

                    if output_items and isinstance(output_items[0], dict):
                        first_item = output_items[0]
                        snapshot["output_first_item_keys"] = sorted(first_item.keys())
                        content_keys: list[list[str]] = []
                        if isinstance(first_item.get("content"), list):
                            for block in first_item["content"]:
                                if isinstance(block, dict):
                                    content_keys.append(sorted(block.keys()))
                                    if not text_head and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                                        text_head = block["text"][:200].replace("\n", "\\n")
                        snapshot["output_first_item_content_keys"] = content_keys
                        if text_head:
                            Path("logs/debug/openai_mini_text_head.txt").write_text(text_head, encoding="utf-8")

                debug_path = Path("logs/debug/openai_shape_task_llm_mini.json")
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

            parsed_output = self._extract_structured_json(payload)
            if parsed_output is None:
                text_output = self._extract_text(payload)
                parsed_output = self._parse_text_output(text_output, task_id=task_id)

            validated_obj: Any = parsed_output
            if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                validate_lines = [f"type={type(validated_obj).__name__}"]
                if isinstance(validated_obj, dict):
                    keys = sorted(validated_obj.keys())
                    validate_lines.append(f"keys={keys}")
                    validate_lines.append(f"slides={'slides' in validated_obj}")
                else:
                    validate_lines.append("keys=[]")
                    validate_lines.append("slides=False")
                validate_path = Path("logs/debug/openai_mini_validate_keys.txt")
                validate_path.parent.mkdir(parents=True, exist_ok=True)
                validate_path.write_text("\n".join(validate_lines) + "\n", encoding="utf-8")

            if self.force_json_schema is not None:
                if not isinstance(validated_obj, dict):
                    raise ValueError("schema validation failed: output is not an object")
                required = hardened_schema.get("required", [])
                if isinstance(required, list):
                    for field in required:
                        if isinstance(field, str) and field not in validated_obj:
                            raise ValueError(f"schema validation failed: '{field}' is a required property")

            usage = payload.get("usage", {})
            return {
                "ok": True,
                "output": validated_obj,
                "usage": {
                    "time_ms": int((time.monotonic() - start) * 1000),
                    "tokens_in": int(usage.get("input_tokens", 0)),
                    "tokens_out": int(usage.get("output_tokens", 0)),
                },
                "meta": {"adapter": "openai", "model": self.model},
            }
        except (requests.RequestException, ValueError) as exc:
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
        output_items = payload.get("output", [])
        if isinstance(output_items, list):
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message":
                    continue
                content_blocks = item.get("content", [])
                if not isinstance(content_blocks, list):
                    continue
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                        extracted = block["text"]
                        if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                            head = extracted[:200].replace("\n", "\\n")
                            debug_path = Path("logs/debug/openai_mini_extracted_text_head.txt")
                            debug_path.parent.mkdir(parents=True, exist_ok=True)
                            debug_path.write_text(head, encoding="utf-8")
                        return extracted

        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text:
            if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                head = output_text[:200].replace("\n", "\\n")
                debug_path = Path("logs/debug/openai_mini_extracted_text_head.txt")
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(head, encoding="utf-8")
            return output_text

        nested = payload.get("response")
        if isinstance(nested, dict):
            nested_text = nested.get("output_text")
            if isinstance(nested_text, str) and nested_text:
                if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                    head = nested_text[:200].replace("\n", "\\n")
                    debug_path = Path("logs/debug/openai_mini_extracted_text_head.txt")
                    debug_path.parent.mkdir(parents=True, exist_ok=True)
                    debug_path.write_text(head, encoding="utf-8")
                return nested_text

        raise ValueError("OpenAI response did not include textual JSON output")

    @classmethod
    def _extract_structured_json(cls, resp_json: dict[str, Any]) -> dict[str, Any] | None:
        def parse_maybe_dict(value: Any) -> dict[str, Any] | None:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed.startswith("{") and trimmed.endswith("}"):
                    try:
                        parsed = json.loads(trimmed)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        return None
            return None

        for key in ("output_json", "json", "structured"):
            parsed = parse_maybe_dict(resp_json.get(key))
            if parsed is not None:
                return parsed

        output_items = resp_json.get("output")
        if isinstance(output_items, list):
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                for key in ("output_json", "json", "structured", "arguments"):
                    parsed = parse_maybe_dict(item.get(key))
                    if parsed is not None:
                        return parsed

                content = item.get("content")
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        block_type = str(block.get("type", ""))
                        if block_type == "output_text" and isinstance(block.get("text"), str):
                            text_value = block["text"]
                            try:
                                parsed = json.loads(text_value)
                                if isinstance(parsed, dict):
                                    return parsed
                            except json.JSONDecodeError:
                                start = text_value.find("{")
                                end = text_value.rfind("}")
                                if start >= 0 and end > start:
                                    try:
                                        recovered = json.loads(text_value[start : end + 1])
                                        if isinstance(recovered, dict):
                                            return recovered
                                    except json.JSONDecodeError:
                                        pass
                        if block_type in {"output_json", "json", "structured", "tool_call", "message"}:
                            for key in ("json", "output_json", "structured", "arguments", "text", "value"):
                                parsed = parse_maybe_dict(block.get(key))
                                if parsed is not None:
                                    return parsed

        output_text = resp_json.get("output_text")
        parsed = parse_maybe_dict(output_text)
        if parsed is not None:
            return parsed

        nested = resp_json.get("response")
        if isinstance(nested, dict):
            return cls._extract_structured_json(nested)

        return None

    @staticmethod
    def _parse_text_output(text_output: str, *, task_id: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text_output)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            start = text_output.find("{")
            end = text_output.rfind("}")

            if start >= 0 and end > start:
                try:
                    recovered = json.loads(text_output[start : end + 1])
                    if isinstance(recovered, dict):
                        return recovered
                except json.JSONDecodeError:
                    pass

            if end >= 0:
                try:
                    trimmed = text_output[: end + 1]
                    recovered = json.loads(trimmed)
                    if isinstance(recovered, dict):
                        return recovered
                except json.JSONDecodeError:
                    pass

            if os.getenv("KORA_DEBUG_OPENAI_SHAPE", "") == "1":
                first_char = text_output[0] if text_output else ""
                last_char = text_output[-1] if text_output else ""
                debug = {
                    "msg": exc.msg,
                    "lineno": exc.lineno,
                    "colno": exc.colno,
                    "pos": exc.pos,
                    "len": len(text_output),
                    "first_char": first_char,
                    "last_char": last_char,
                }
                debug_path = Path("logs/debug/openai_mini_jsondecode.txt")
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(json.dumps(debug, indent=2), encoding="utf-8")

        return {
            "status": "ok",
            "task_id": task_id,
            "answer": text_output,
        }


class OpenAIMiniAdapter(OpenAIAdapter):
    """OpenAI adapter bound to the mini-stage model."""

    def __init__(self) -> None:
        mini_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "task_id": {"type": "string"},
                "slides": {
                    "type": "array",
                    "minItems": 18,
                    "maxItems": 18,
                    "items": {
                        "type": "object",
                        "properties": {
                            "i": {"type": "integer"},
                            "title": {"type": "string"},
                            "msg": {"type": "string"},
                        },
                        "required": ["i", "title", "msg"],
                    },
                },
            },
            "required": ["status", "task_id", "slides"],
        }
        super().__init__(
            model=os.getenv("KORA_OPENAI_MODEL_MINI", "gpt-4o-mini"),
            force_json_schema=mini_schema,
            max_output_tokens=3000,
        )


class OpenAIFullAdapter(OpenAIAdapter):
    """OpenAI adapter bound to the full-stage model."""

    def __init__(self) -> None:
        super().__init__(model=os.getenv("KORA_OPENAI_MODEL_FULL", "gpt-4o"))
