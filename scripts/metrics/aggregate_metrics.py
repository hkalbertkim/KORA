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


def parse_kora_mode(mode: str) -> tuple[str, str | None]:
    suffix = mode.split(":", 1)[1] if ":" in mode else ""
    if "#" in suffix:
        profile, trial_id = suffix.split("#", 1)
        return profile, trial_id
    return suffix, None


def get_profile_from_row(row: dict[str, object]) -> str:
    profile = row.get("profile")
    if isinstance(profile, str) and profile:
        return profile
    mode = str(row.get("mode", ""))
    parsed_profile, _ = parse_kora_mode(mode)
    return parsed_profile if parsed_profile else "unknown"


def get_trial_from_row(row: dict[str, object]) -> str | None:
    trial_id = row.get("trial_id")
    if isinstance(trial_id, str) and trial_id:
        return trial_id
    mode = str(row.get("mode", ""))
    _, parsed_trial = parse_kora_mode(mode)
    return parsed_trial


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


def lower_is_better_improvement(baseline: float, profile_value: float) -> float:
    return safe_div(baseline - profile_value, baseline)


def higher_is_better_improvement(baseline: float, profile_value: float) -> float:
    return safe_div(profile_value - baseline, baseline)


def print_sweep_top5(
    rows_by_mode: dict[str, list[dict[str, object]]],
    stats: dict[str, dict[str, float]],
) -> None:
    baseline_full = stats["baseline_full"]
    baseline_staged = stats["baseline_staged"]
    coverage_floor = baseline_staged["coverage_ok_rate"] - 0.02

    trial_records: list[dict[str, object]] = []
    for mode, rows in rows_by_mode.items():
        if not is_kora_mode(mode):
            continue
        profile = get_profile_from_row(rows[0]) if rows else "unknown"
        trial_id = get_trial_from_row(rows[0]) if rows else None
        if not trial_id:
            continue
        s = stats[mode]
        if s["coverage_ok_rate"] < coverage_floor:
            continue

        full_called_reduction_vs_staged = lower_is_better_improvement(
            baseline_staged["full_called_rate"], s["full_called_rate"]
        )
        cost_improvement_vs_staged = lower_is_better_improvement(
            baseline_staged["mean_cost"], s["mean_cost"]
        )
        p95_improvement_vs_staged = lower_is_better_improvement(
            baseline_staged["p95_latency"], s["p95_latency"]
        )
        score = (
            0.45 * full_called_reduction_vs_staged
            + 0.35 * cost_improvement_vs_staged
            + 0.20 * p95_improvement_vs_staged
        )

        params = rows[0].get("params")
        trial_records.append(
            {
                "profile": profile,
                "trial_id": trial_id,
                "full_called_rate": s["full_called_rate"],
                "pct_gate": s["pct_gate"],
                "pct_full": s["pct_full"],
                "mean_cost": s["mean_cost"],
                "p95_latency": s["p95_latency"],
                "coverage_ok_rate": s["coverage_ok_rate"],
                "score": score,
                "params": params if isinstance(params, dict) else {},
            }
        )

    trial_records.sort(
        key=lambda r: (float(r["score"]), float(r["coverage_ok_rate"])),
        reverse=True,
    )
    top_records = trial_records[:5]

    print("Sweep ranking (coverage-constrained)")
    print(f"Coverage constraint: coverage_ok_rate >= {coverage_floor * 100:.2f}%")
    print(
        "profile      trial_id  full_called%  pct_gate  pct_full  mean_cost   p95_ms  coverage_ok%   score  params"
    )
    if not top_records:
        print("(no trials passed coverage constraint)")
        print("")
        return
    for rec in top_records:
        params_json = json.dumps(rec["params"], sort_keys=True, separators=(",", ":"))
        print(
            f"{str(rec['profile']):<12} {str(rec['trial_id']):<8} "
            f"{fmt_pct(float(rec['full_called_rate'])):>11}  {fmt_pct(float(rec['pct_gate'])):>8}  "
            f"{fmt_pct(float(rec['pct_full'])):>8}  {float(rec['mean_cost']):>9.2f}  "
            f"{float(rec['p95_latency']):>7.2f}  {fmt_pct(float(rec['coverage_ok_rate'])):>11}  "
            f"{float(rec['score']):>6.4f}  {params_json}"
        )
    print("")
    print("Baseline staged reference")
    print(
        f"full_called={fmt_pct(baseline_staged['full_called_rate'])}, "
        f"mean_cost={baseline_staged['mean_cost']:.2f}, "
        f"p95={baseline_staged['p95_latency']:.2f}, "
        f"coverage_ok={fmt_pct(baseline_staged['coverage_ok_rate'])}"
    )
    print(
        "Score weights: 0.45*full_called_reduction_vs_staged + "
        "0.35*cost_improvement_vs_staged + 0.20*p95_improvement_vs_staged"
    )
    _ = baseline_full


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

    has_sweep_trials = any(
        get_trial_from_row(rows[0]) is not None
        for mode, rows in rows_by_mode.items()
        if is_kora_mode(mode) and rows
    )
    if has_sweep_trials:
        print_sweep_top5(rows_by_mode=rows_by_mode, stats=stats)
        return

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
