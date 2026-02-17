"""Simple token-cost estimation helpers."""

from __future__ import annotations


MODEL_PRICING = {
    "gpt-4o-mini": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.0006,
    }
}


def estimate_cost(
    model: str,
    tokens_in: int,
    tokens_out: int,
    price_input: float | None = None,
    price_output: float | None = None,
) -> float:
    pricing = MODEL_PRICING.get(model, {})
    input_per_1k = float(price_input) if price_input is not None else float(pricing.get("input_per_1k", 0.0))
    output_per_1k = float(price_output) if price_output is not None else float(pricing.get("output_per_1k", 0.0))

    cost = (max(0, int(tokens_in)) / 1000.0) * input_per_1k
    cost += (max(0, int(tokens_out)) / 1000.0) * output_per_1k
    return round(cost, 8)


def compute_savings(direct_cost: float, kora_cost: float) -> dict[str, float]:
    direct = float(direct_cost)
    kora = float(kora_cost)
    savings = direct - kora
    savings_percent = 0.0 if direct <= 0 else (savings / direct) * 100.0
    return {
        "direct_cost_usd": round(direct, 8),
        "kora_cost_usd": round(kora, 8),
        "savings_usd": round(savings, 8),
        "savings_percent": round(savings_percent, 4),
    }
