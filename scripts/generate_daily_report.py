#!/usr/bin/env python3
"""Generate daily KORA report markdown under docs/reports."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    today = date.today().isoformat()
    repo_root = Path(__file__).resolve().parents[1]
    reports_dir = repo_root / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"KORA_DAILY_{today}.md"

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    latest_commit = _run_git(["rev-parse", "--short", "HEAD"])
    last_20 = _run_git(["log", "-20", "--oneline"])

    content = "\n".join(
        [
            f"# KORA Daily Report - {today}",
            "",
            f"Date: {today}",
            "",
            "## Highlights",
            "- Adaptive routing updates completed.",
            "- Added routing profile defaults and profile-driven behavior demos.",
            "- Added conditional self-consistency trigger gating.",
            "- Added VoI scoring and budget-aware escalation gating.",
            "- Updated benchmark runner and README with adaptive routing traces.",
            "",
            "## Git Summary",
            f"- Branch: `{branch}`",
            f"- Latest commit: `{latest_commit}`",
            "",
            "### Last 20 commits (oneline)",
            "```text",
            last_20,
            "```",
            "",
        ]
    )

    report_path.write_text(content, encoding="utf-8")
    print(f"Report written: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
