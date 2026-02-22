#!/usr/bin/env python3
"""Synthetic metrics harness for KORA KPI proof package."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


BASELINE_MODES = ("baseline_full", "baseline_staged")
DEFAULT_PROFILES = ("balanced", "cost", "reliability", "latency")
ALLOWED_PROFILES = set(DEFAULT_PROFILES)


@dataclass(frozen=True)
class RequestParams:
    request_id: int
    difficulty: float
    mini_conf: float
    gate_conf: float
    full_conf: float
    mini_latency_ms: float
    gate_latency_ms: float
    full_latency_ms: float
    mini_cost_units: float
    gate_cost_units: float
    full_cost_units: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def generate_request_params(n: int, seed: int) -> list[RequestParams]:
    rng = random.Random(seed)
    workload: list[RequestParams] = []
    for request_id in range(1, n + 1):
        difficulty = rng.random()
        mini_conf = _clamp(
            0.96 - 0.70 * difficulty + rng.uniform(-0.05, 0.05),
            0.01,
            0.99,
        )
        gate_conf = _clamp(
            mini_conf + 0.15 * (1.0 - difficulty) + rng.uniform(-0.04, 0.04),
            0.01,
            0.995,
        )
        full_conf = _clamp(
            gate_conf + 0.20 * (1.0 - difficulty) + rng.uniform(-0.03, 0.03),
            0.01,
            0.999,
        )

        mini_latency_ms = _clamp(65 + 170 * difficulty + rng.uniform(-12, 12), 30, 500)
        gate_latency_ms = _clamp(95 + 210 * difficulty + rng.uniform(-15, 15), 50, 700)
        full_latency_ms = _clamp(
            420 + 850 * difficulty + rng.uniform(-40, 40),
            200,
            2200,
        )

        mini_cost_units = _clamp(85 + 140 * difficulty + rng.uniform(-10, 10), 40, 320)
        gate_cost_units = _clamp(130 + 180 * difficulty + rng.uniform(-10, 10), 60, 430)
        full_cost_units = _clamp(
            1200 + 2200 * difficulty + rng.uniform(-40, 40),
            800,
            5000,
        )

        workload.append(
            RequestParams(
                request_id=request_id,
                difficulty=difficulty,
                mini_conf=mini_conf,
                gate_conf=gate_conf,
                full_conf=full_conf,
                mini_latency_ms=mini_latency_ms,
                gate_latency_ms=gate_latency_ms,
                full_latency_ms=full_latency_ms,
                mini_cost_units=mini_cost_units,
                gate_cost_units=gate_cost_units,
                full_cost_units=full_cost_units,
            )
        )
    return workload


def _stable_profile_bias(profile: str | None) -> int:
    if not profile:
        return 0
    return sum((idx + 1) * ord(ch) for idx, ch in enumerate(profile))


def _mode_rng(seed: int, request_id: int, mode: str, profile: str | None) -> random.Random:
    mode_bias_lookup = {"baseline_full": 0, "baseline_staged": 1, "kora_adaptive": 2}
    mode_bias = mode_bias_lookup[mode] * 1543
    profile_bias = _stable_profile_bias(profile) * 17
    return random.Random(seed * 100_003 + request_id * 97 + mode_bias + profile_bias)


def _simulate_kora_adaptive(
    req: RequestParams,
    profile: str,
    stages_called: list[str],
) -> tuple[float, float]:
    total_cost_units = 0.0
    total_latency_ms = 0.0
    stages_called.append("mini")
    total_cost_units += req.mini_cost_units
    total_latency_ms += req.mini_latency_ms
    mini_conf = req.mini_conf

    profile_params = {
        "balanced": {
            "voi_threshold": 0.12,
            "mini_full_threshold": 0.80,
            "gate_full_threshold": 0.90,
            "budget_scale": 1.25,
            "allow_self_consistency": True,
        },
        "cost": {
            "voi_threshold": 0.17,
            "mini_full_threshold": 0.74,
            "gate_full_threshold": 0.84,
            "budget_scale": 1.08,
            "allow_self_consistency": False,
        },
        "reliability": {
            "voi_threshold": 0.08,
            "mini_full_threshold": 0.88,
            "gate_full_threshold": 0.95,
            "budget_scale": 1.48,
            "allow_self_consistency": True,
        },
        "latency": {
            "voi_threshold": 0.20,
            "mini_full_threshold": 0.70,
            "gate_full_threshold": 0.80,
            "budget_scale": 1.12,
            "allow_self_consistency": False,
        },
    }[profile]

    next_stage_cost_high = req.full_cost_units > 2200
    if (
        profile_params["allow_self_consistency"]
        and next_stage_cost_high
        and 0.50 <= mini_conf < 0.82
    ):
        # Conditional self-consistency: sample mini once more for expensive paths.
        stages_called.append("mini")
        total_cost_units += req.mini_cost_units * 0.95
        total_latency_ms += req.mini_latency_ms * 0.90
        mini_conf = _clamp(mini_conf + 0.08 * (1.0 - mini_conf), 0.01, 0.995)

    voi_gain = (1.0 - mini_conf) * (0.35 + 0.95 * req.difficulty)
    budget_limit = req.full_cost_units * profile_params["budget_scale"] + 280
    can_escalate_gate = total_cost_units + req.gate_cost_units <= budget_limit
    should_escalate_gate = (
        voi_gain > profile_params["voi_threshold"] and mini_conf < 0.90 and can_escalate_gate
    )

    gate_conf = req.gate_conf
    if should_escalate_gate:
        stages_called.append("gate")
        total_cost_units += req.gate_cost_units
        total_latency_ms += req.gate_latency_ms
        gate_conf = _clamp(gate_conf + 0.02 * (1.0 - req.difficulty), 0.01, 0.997)

    can_escalate_full = total_cost_units + req.full_cost_units <= budget_limit * 1.05
    if "gate" in stages_called:
        should_escalate_full = (
            gate_conf < profile_params["gate_full_threshold"] and can_escalate_full
        )
    else:
        should_escalate_full = (
            mini_conf < profile_params["mini_full_threshold"] and can_escalate_full
        )

    if should_escalate_full:
        stages_called.append("full")
        total_cost_units += req.full_cost_units
        total_latency_ms += req.full_latency_ms

    return total_cost_units, total_latency_ms


def simulate_mode(
    req: RequestParams,
    mode: str,
    seed: int,
    profile: str | None = None,
) -> dict[str, object]:
    rng = _mode_rng(seed, req.request_id, mode, profile)
    stages_called: list[str] = []
    total_cost_units = 0.0
    total_latency_ms = 0.0

    if mode == "baseline_full":
        stages_called.append("full")
        total_cost_units += req.full_cost_units
        total_latency_ms += req.full_latency_ms
    elif mode == "baseline_staged":
        stages_called.append("mini")
        total_cost_units += req.mini_cost_units
        total_latency_ms += req.mini_latency_ms
        if req.mini_conf < 0.85:
            stages_called.append("full")
            total_cost_units += req.full_cost_units
            total_latency_ms += req.full_latency_ms
    elif mode == "kora_adaptive":
        if not profile:
            raise ValueError("kora_adaptive requires a profile")
        total_cost_units, total_latency_ms = _simulate_kora_adaptive(
            req=req,
            profile=profile,
            stages_called=stages_called,
        )
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    full_called = "full" in stages_called
    if full_called:
        verify_prob = _clamp(0.95 - 0.28 * req.difficulty, 0.45, 0.995)
    elif "gate" in stages_called:
        verify_prob = _clamp(0.83 - 0.46 * req.difficulty, 0.20, 0.93)
    else:
        verify_prob = _clamp(0.74 - 0.60 * req.difficulty + 0.08 * req.mini_conf, 0.12, 0.90)

    verify_ok = rng.random() < verify_prob

    if full_called:
        quality_prob = _clamp(0.94 - 0.22 * req.difficulty + 0.05 * req.full_conf, 0.50, 0.995)
    elif "gate" in stages_called:
        quality_prob = _clamp(0.83 - 0.38 * req.difficulty + 0.07 * req.gate_conf, 0.25, 0.95)
    else:
        quality_prob = _clamp(0.72 - 0.54 * req.difficulty + 0.10 * req.mini_conf, 0.15, 0.90)
    quality_ok = rng.random() < quality_prob
    coverage_ok = verify_ok and quality_ok

    mode_name = mode if mode != "kora_adaptive" else f"kora_adaptive:{profile}"

    return {
        "request_id": req.request_id,
        "mode": mode_name,
        "profile": profile,
        "full_called": full_called,
        "stages_called": stages_called,
        "total_cost_units": round(total_cost_units, 3),
        "total_latency_ms": round(total_latency_ms, 3),
        "verify_ok": verify_ok,
        "quality_ok": quality_ok,
        "coverage_ok": coverage_ok,
    }


def parse_profiles(raw_profiles: str) -> list[str]:
    profiles = [p.strip() for p in raw_profiles.split(",") if p.strip()]
    if not profiles:
        raise ValueError("--profiles produced an empty profile list")
    unknown_profiles = [p for p in profiles if p not in ALLOWED_PROFILES]
    if unknown_profiles:
        raise ValueError(
            f"Unknown profile(s): {', '.join(unknown_profiles)}; allowed: {', '.join(DEFAULT_PROFILES)}"
        )
    return profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic KORA metrics harness.")
    parser.add_argument("--n", type=int, default=1000, help="Number of synthetic requests.")
    parser.add_argument("--seed", type=int, default=1337, help="Seed for deterministic run.")
    parser.add_argument(
        "--profiles",
        type=str,
        default="balanced,cost,reliability,latency",
        help="Comma-separated KORA routing profiles.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output path. Default: artifacts/metrics/harness_<DATE>.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.n <= 0:
        raise ValueError("--n must be > 0")
    profiles = parse_profiles(args.profiles)

    datestamp = datetime.now().strftime("%Y%m%d")
    output_path = args.output or Path("artifacts/metrics") / f"harness_{datestamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workload = generate_request_params(n=args.n, seed=args.seed)

    with output_path.open("w", encoding="utf-8") as f:
        for req in workload:
            for mode in BASELINE_MODES:
                result = simulate_mode(req=req, mode=mode, seed=args.seed, profile=None)
                f.write(json.dumps(result, sort_keys=True) + "\n")
            for profile in profiles:
                result = simulate_mode(
                    req=req,
                    mode="kora_adaptive",
                    profile=profile,
                    seed=args.seed,
                )
                f.write(json.dumps(result, sort_keys=True) + "\n")

    print(str(output_path))


if __name__ == "__main__":
    main()
