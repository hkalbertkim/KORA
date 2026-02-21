#!/usr/bin/env python3
"""Aggregate KPI metrics from synthetic harness JSONL output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_MODES = ("baseline_full", "baseline_staged", "kora_adaptive")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate KPI metrics from harness output.")
    parser.add_argument("jsonl_path", type=Path, help="Path to harness JSONL file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.jsonl_path.exists():
        raise FileNotFoundError(f"Input file not found: {args.jsonl_path}")

    rows_by_mode: dict[str, list[dict[str, object]]] = {m: [] for m in EXPECTED_MODES}
    with args.jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            mode = row.get("mode")
            if mode in rows_by_mode:
                rows_by_mode[mode].append(row)

    missing_modes = [mode for mode, rows in rows_by_mode.items() if not rows]
    if missing_modes:
        raise ValueError(f"Missing data for mode(s): {', '.join(missing_modes)}")

    stats: dict[str, dict[str, float]] = {}
    for mode, rows in rows_by_mode.items():
        n = len(rows)
        full_rate = safe_div(
            sum(1 for r in rows if bool(r["full_called"])),
            n,
        )
        mean_cost = safe_div(sum(float(r["total_cost_units"]) for r in rows), n)
        p95_latency = percentile([float(r["total_latency_ms"]) for r in rows], 0.95)
        coverage_rate = safe_div(
            sum(1 for r in rows if bool(r["coverage_ok"])),
            n,
        )
        stats[mode] = {
            "count": float(n),
            "full_rate": full_rate,
            "mean_cost": mean_cost,
            "p95_latency": p95_latency,
            "coverage_rate": coverage_rate,
        }

    baseline_full = stats["baseline_full"]
    baseline_staged = stats["baseline_staged"]
    kora = stats["kora_adaptive"]

    esc_reduction_vs_full = safe_div(
        baseline_full["full_rate"] - kora["full_rate"],
        baseline_full["full_rate"],
    )
    esc_reduction_vs_staged = safe_div(
        baseline_staged["full_rate"] - kora["full_rate"],
        baseline_staged["full_rate"],
    )
    cost_delta_vs_full = safe_div(
        baseline_full["mean_cost"] - kora["mean_cost"],
        baseline_full["mean_cost"],
    )
    cost_delta_vs_staged = safe_div(
        baseline_staged["mean_cost"] - kora["mean_cost"],
        baseline_staged["mean_cost"],
    )
    latency_delta_vs_full = safe_div(
        baseline_full["p95_latency"] - kora["p95_latency"],
        baseline_full["p95_latency"],
    )
    latency_delta_vs_staged = safe_div(
        baseline_staged["p95_latency"] - kora["p95_latency"],
        baseline_staged["p95_latency"],
    )

    print(f"Input: {args.jsonl_path}")
    print("")
    print(
        "mode             count  full_called%  mean_cost_units  p95_latency_ms  coverage_ok%"
    )
    for mode in EXPECTED_MODES:
        s = stats[mode]
        print(
            f"{mode:<16} {int(s['count']):>5}  {fmt_pct(s['full_rate']):>11}  "
            f"{s['mean_cost']:>15.2f}  {s['p95_latency']:>14.2f}  "
            f"{fmt_pct(s['coverage_rate']):>11}"
        )

    print("")
    print("KPI deltas (kora_adaptive):")
    print(
        f"- full-model escalation reduction vs baseline_full:   {fmt_pct(esc_reduction_vs_full)}"
    )
    print(
        f"- full-model escalation reduction vs baseline_staged: {fmt_pct(esc_reduction_vs_staged)}"
    )
    print(f"- total cost delta vs baseline_full:                  {fmt_pct(cost_delta_vs_full)}")
    print(
        f"- total cost delta vs baseline_staged:                {fmt_pct(cost_delta_vs_staged)}"
    )
    print(
        f"- p95 latency delta vs baseline_full:                 {fmt_pct(latency_delta_vs_full)}"
    )
    print(
        f"- p95 latency delta vs baseline_staged:               {fmt_pct(latency_delta_vs_staged)}"
    )
    print(f"- workload coverage (kora_adaptive):                  {fmt_pct(kora['coverage_rate'])}")


if __name__ == "__main__":
    main()
