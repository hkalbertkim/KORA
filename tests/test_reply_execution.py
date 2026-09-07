import json
from pathlib import Path

import pytest

from kora.benchmarks import direct_baseline, three_system


@pytest.mark.parametrize("invalid", [False, True])
def test_reply_contract_preserves_model_activity(monkeypatch, invalid):
    data = json.loads(
        Path("examples/benchmarks/three-environment/s3-workloads.json").read_text()
    )
    fixture = next(c for c in data["cases"] if c.get("model_contract") == "reply-v1")

    class Backend:
        def __init__(self, **kwargs):
            pass

        def health(self):
            return {}

        def generate(self, payload):
            assert payload["system"] == fixture["system_prompt"]
            output = dict(fixture["expected_model_output"])
            if invalid:
                output["reply"] = "Your refund was already processed."
            return {"text": json.dumps(output), "completion_tokens": 30}

    monkeypatch.setattr(three_system, "ModelBackend", Backend)
    monkeypatch.setattr(direct_baseline, "ModelBackend", Backend)
    native = three_system.execute_case(
        "h100", {"backend": {}}, fixture, "unused", "M", "reply", lambda e: None
    )
    direct = direct_baseline.execute_direct({}, fixture, "unused")
    for result in (native, direct):
        assert result["quality_pass"] is not invalid
        assert result["model_calls_completed"] == 1
        assert result["completion_tokens"] == 30
