#!/usr/bin/env python3
"""Aggregate KPI metrics from synthetic harness JSONL output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASELINE_MODES = ("baseline_full", "baseline_staged")


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


def is_kora_mode(mode: str) -> bool:
    return mode.startswith("kora_adaptive:")


def get_profile_from_row(row: dict[str, object]) -> str:
    profile = row.get("profile")
    if isinstance(profile, str) and profile:
        return profile
    mode = str(row.get("mode", ""))
    _, _, suffix = mode.partition(":")
    return suffix if suffix else "unknown"


def compute_stats(rows: list[dict[str, object]]) -> dict[str, float]:
    n = len(rows)
    latencies = [float(r["total_latency_ms"]) for r in rows]
    latencies_full = [float(r["total_latency_ms"]) for r in rows if bool(r["full_called"])]
    latencies_no_full = [float(r["total_latency_ms"]) for r in rows if not bool(r["full_called"])]

    pct_mini = safe_div(
        sum(1 for r in rows if "mini" in r.get("stages_called", [])),
        n,
    )
    pct_gate = safe_div(
        sum(1 for r in rows if "gate" in r.get("stages_called", [])),
        n,
    )
    pct_full = safe_div(
        sum(1 for r in rows if "full" in r.get("stages_called", [])),
        n,
    )
    avg_num_stages_called = safe_div(
        sum(len(r.get("stages_called", [])) for r in rows),
        n,
    )

    return {
        "count": float(n),
        "full_called_rate": safe_div(sum(1 for r in rows if bool(r["full_called"])), n),
        "mean_cost": safe_div(sum(float(r["total_cost_units"]) for r in rows), n),
        "latency_min_ms": min(latencies) if latencies else 0.0,
        "latency_mean_ms": safe_div(sum(latencies), n),
        "latency_max_ms": max(latencies) if latencies else 0.0,
        "p50_latency": percentile(latencies, 0.50),
        "p95_latency": percentile(latencies, 0.95),
        "p99_latency": percentile(latencies, 0.99),
        "p95_latency_full_called": percentile(latencies_full, 0.95),
        "p95_latency_no_full": percentile(latencies_no_full, 0.95),
        "verify_ok_rate": safe_div(sum(1 for r in rows if bool(r["verify_ok"])), n),
        "quality_ok_rate": safe_div(sum(1 for r in rows if bool(r["quality_ok"])), n),
        "coverage_ok_rate": safe_div(sum(1 for r in rows if bool(r.get("coverage_ok", False))), n),
        "pct_mini": pct_mini,
        "pct_gate": pct_gate,
        "pct_full": pct_full,
        "avg_num_stages_called": avg_num_stages_called,
    }


def print_mode_table(stats: dict[str, dict[str, float]], mode_order: list[str]) -> None:
    print(
        "mode                     count  full_called%  mean_cost  p50_ms   p95_ms   p99_ms  verify_ok%  quality_ok%  coverage_ok%"
    )
    for mode in mode_order:
        s = stats[mode]
        print(
            f"{mode:<24} {int(s['count']):>5}  {fmt_pct(s['full_called_rate']):>11}  "
            f"{s['mean_cost']:>9.2f}  {s['p50_latency']:>6.2f}  {s['p95_latency']:>7.2f}  "
            f"{s['p99_latency']:>7.2f}  {fmt_pct(s['verify_ok_rate']):>10}  {fmt_pct(s['quality_ok_rate']):>11}  "
            f"{fmt_pct(s['coverage_ok_rate']):>11}"
        )


def print_delta_table(
    profile_mode: str,
    profile_stats: dict[str, float],
    baseline_full: dict[str, float],
    baseline_staged: dict[str, float],
) -> None:
    metrics = [
        ("full_called_rate", "full_called%"),
        ("mean_cost", "mean_cost"),
        ("p50_latency", "p50_latency"),
        ("p95_latency", "p95_latency"),
        ("p99_latency", "p99_latency"),
        ("verify_ok_rate", "verify_ok%"),
        ("quality_ok_rate", "quality_ok%"),
        ("coverage_ok_rate", "coverage_ok%"),
    ]
    lower_is_better = {
        "full_called_rate",
        "mean_cost",
        "p50_latency",
        "p95_latency",
        "p99_latency",
    }
    print(f"Improvements for {profile_mode} (positive = better)")
    print("metric             vs_baseline_full   vs_baseline_staged")
    for key, label in metrics:
        if key in lower_is_better:
            improvement_vs_full = safe_div(
                baseline_full[key] - profile_stats[key], baseline_full[key]
            )
            improvement_vs_staged = safe_div(
                baseline_staged[key] - profile_stats[key], baseline_staged[key]
            )
        else:
            improvement_vs_full = safe_div(
                profile_stats[key] - baseline_full[key], baseline_full[key]
            )
            improvement_vs_staged = safe_div(
                profile_stats[key] - baseline_staged[key], baseline_staged[key]
            )
        print(
            f"{label:<18} {fmt_pct(improvement_vs_full):>16}   {fmt_pct(improvement_vs_staged):>18}"
        )
    print("")


def print_sanity_table(stats: dict[str, dict[str, float]], mode_order: list[str]) -> None:
    print("Latency sanity by mode")
    print(
        "mode                     latency_min_ms  latency_mean_ms  latency_max_ms  p95_full_called_ms  p95_no_full_ms"
    )
    for mode in mode_order:
        s = stats[mode]
        print(
            f"{mode:<24} {s['latency_min_ms']:>14.2f}  {s['latency_mean_ms']:>15.2f}  "
            f"{s['latency_max_ms']:>14.2f}  {s['p95_latency_full_called']:>18.2f}  {s['p95_latency_no_full']:>14.2f}"
        )
    print("")


def print_stage_mix_table(stats: dict[str, dict[str, float]], mode_order: list[str]) -> None:
    print("Stage mix by mode")
    print("mode                     pct_mini  pct_gate  pct_full  avg_num_stages_called")
    for mode in mode_order:
        s = stats[mode]
        print(
            f"{mode:<24} {fmt_pct(s['pct_mini']):>8}  {fmt_pct(s['pct_gate']):>8}  "
            f"{fmt_pct(s['pct_full']):>8}  {s['avg_num_stages_called']:>21.3f}"
        )
    print("")


def main() -> None:
    args = parse_args()
    if not args.jsonl_path.exists():
        raise FileNotFoundError(f"Input file not found: {args.jsonl_path}")

    rows_by_mode: dict[str, list[dict[str, object]]] = {}
    kora_profiles: set[str] = set()
    with args.jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            mode = str(row.get("mode", ""))
            rows_by_mode.setdefault(mode, []).append(row)
            if is_kora_mode(mode):
                kora_profiles.add(get_profile_from_row(row))

    missing_modes = [mode for mode in BASELINE_MODES if not rows_by_mode.get(mode)]
    if missing_modes:
        raise ValueError(f"Missing data for mode(s): {', '.join(missing_modes)}")
    if not kora_profiles:
        raise ValueError("No kora_adaptive:<profile> rows found in input")

    stats: dict[str, dict[str, float]] = {}
    for mode, rows in rows_by_mode.items():
        stats[mode] = compute_stats(rows)

    baseline_full = stats["baseline_full"]
    baseline_staged = stats["baseline_staged"]

    print(f"Input: {args.jsonl_path}")
    print("")

    for profile in sorted(kora_profiles):
        profile_mode = f"kora_adaptive:{profile}"
        if profile_mode not in stats:
            continue
        print(f"Profile: {profile}")
        mode_order = ["baseline_full", "baseline_staged", profile_mode]
        print_mode_table(stats, mode_order)
        print("")
        print_sanity_table(stats, mode_order)
        print_stage_mix_table(stats, mode_order)
        print_delta_table(
            profile_mode=profile_mode,
            profile_stats=stats[profile_mode],
            baseline_full=baseline_full,
            baseline_staged=baseline_staged,
        )


if __name__ == "__main__":
    main()
