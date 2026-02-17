"""KORA command-line utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kora.telemetry import load_json, summarize_run


def _default_json_out(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.telemetry.json")


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

    args = parser.parse_args(argv)

    if args.command == "telemetry":
        input_path = Path(args.input)
        obj = load_json(input_path)
        summary = summarize_run(obj)
        json_out = Path(args.json_out) if args.json_out else _default_json_out(input_path)
        json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _print_summary(summary)
        print(f"Saved telemetry JSON: {json_out}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
