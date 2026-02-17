"""KORA command-line utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kora.cost_model import compute_savings
from kora.telemetry import load_json, render_markdown_report, summarize_run


def _default_json_out(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.telemetry.json")


def _default_md_out(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.telemetry.md")


def _print_summary(summary: dict) -> None:
    print("Telemetry Summary")
    print(f"- ok: {summary['ok']}")
    print(f"- total_time_ms: {summary['total_time_ms']}")
    print(f"- total_llm_calls: {summary['total_llm_calls']}")
    print(f"- tokens_in: {summary['tokens_in']}")
    print(f"- tokens_out: {summary['tokens_out']}")
    print(f"- events_ok: {summary['events_ok']}")
    print(f"- events_fail: {summary['events_fail']}")
    print(f"- events_skipped: {summary['events_skipped']}")
    print(f"- budget_breaches: {summary['budget_breaches']}")
    print(f"- escalation_required: {summary['escalation_required']}")
    if "estimated_cost_usd" in summary:
        print(f"- model: {summary.get('model', '')}")
        print(f"- estimated_cost_usd: {summary['estimated_cost_usd']}")
    print("- stage_counts:")
    if summary["stage_counts"]:
        for stage, count in sorted(summary["stage_counts"].items()):
            print(f"  - {stage}: {count}")
    else:
        print("  - (none)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kora.cli", description="KORA CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    telemetry_parser = subparsers.add_parser("telemetry", help="summarize a run JSON file")
    telemetry_parser.add_argument("--input", required=True, help="path to run/report JSON")
    telemetry_parser.add_argument("--json-out", help="output path for telemetry JSON")
    telemetry_parser.add_argument("--md-out", help="output path for telemetry markdown report")
    telemetry_parser.add_argument("--price-input", type=float, help="override input price per 1k tokens")
    telemetry_parser.add_argument("--price-output", type=float, help="override output price per 1k tokens")
    telemetry_parser.add_argument("--compare", help="optional second run/report JSON to compute savings delta")

    args = parser.parse_args(argv)

    if args.command == "telemetry":
        input_path = Path(args.input)
        obj = load_json(input_path)
        summary = summarize_run(obj, price_input=args.price_input, price_output=args.price_output)
        json_out = Path(args.json_out) if args.json_out else _default_json_out(input_path)
        md_out = Path(args.md_out) if args.md_out else _default_md_out(input_path)

        savings: dict | None = None
        compare_path: Path | None = None
        if args.compare:
            compare_path = Path(args.compare)
            compare_obj = load_json(compare_path)
            compare_summary = summarize_run(
                compare_obj,
                price_input=args.price_input,
                price_output=args.price_output,
            )
            input_mode = str(obj.get("mode", "")).lower()
            compare_mode = str(compare_obj.get("mode", "")).lower()

            input_cost = float(summary.get("estimated_cost_usd", 0.0))
            compare_cost = float(compare_summary.get("estimated_cost_usd", 0.0))
            if input_mode == "kora" and compare_mode == "direct":
                savings = compute_savings(compare_cost, input_cost)
            elif input_mode == "direct" and compare_mode == "kora":
                savings = compute_savings(input_cost, compare_cost)
            else:
                savings = compute_savings(compare_cost, input_cost)
            summary["savings"] = savings

        json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        md_report = render_markdown_report(
            summary,
            source_path=str(input_path),
            compare_path=str(compare_path) if compare_path else None,
            savings=savings,
        )
        md_out.write_text(md_report, encoding="utf-8")
        _print_summary(summary)
        if savings is not None:
            print("Savings Summary")
            print(f"- direct_cost_usd: {savings['direct_cost_usd']}")
            print(f"- kora_cost_usd: {savings['kora_cost_usd']}")
            print(f"- savings_usd: {savings['savings_usd']}")
            print(f"- savings_percent: {savings['savings_percent']}")
        print(f"Saved telemetry JSON: {json_out}")
        print(f"Saved telemetry Markdown: {md_out}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
