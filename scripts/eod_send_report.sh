#!/usr/bin/env bash
set -euo pipefail

TODAY="$(date +%F)"
REPORT_PATH="docs/reports/KORA_DAILY_${TODAY}.md"
SUBJECT="KORA Dev ${TODAY} — Daily Report"

python3 scripts/generate_daily_report.py
python3 scripts/send_daily_report_email.py \
  --report "${REPORT_PATH}" \
  --to "hkalbert71@gmail.com" \
  --subject "${SUBJECT}"
