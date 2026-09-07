import pytest

from kora.benchmarks import direct_baseline as baseline


@pytest.mark.parametrize(
    "text,quality,status",
    [
        ('{"category":"billing"}', True, "completed"),
        ('{"category":"access"}', False, "completed"),
        ("not json", False, "failed"),
    ],
)
def test_direct_preserves_actual_calls_on_quality_failure(
    monkeypatch, text, quality, status
):
    class Backend:
        def __init__(self, **config):
            pass

        def health(self):
            pass

        def generate(self, value):
            return {"text": text, "completion_tokens": 10}

    monkeypatch.setattr(baseline, "ModelBackend", Backend)
    fixture = {
        "id": "case",
        "text": "refund",
        "expected_model_output": {"category": "billing"},
    }
    result = baseline.execute_direct({}, fixture, "classify")
    assert result["quality_pass"] is quality
    assert result["status"] == status
    assert result["model_calls_completed"] == 1
    assert result["completion_tokens"] == 10
    assert result["kora_worker_routing"] is False
    assert result["result_reuse"] is False
