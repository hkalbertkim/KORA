#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TODAY="$(date +%F)"
REPORT_PATH="docs/reports/KORA_DAILY_${TODAY}.md"
SUBJECT="KORA Dev ${TODAY} — Daily Report"

echo "[smtp] host=${SMTP_HOST:+set} port=${SMTP_PORT:+set} user=${SMTP_USER:+set} pass=${SMTP_PASS:+set} from=${SMTP_FROM:+set}"

python3 scripts/generate_daily_report.py
python3 scripts/send_daily_report_email.py \
  --report "${REPORT_PATH}" \
  --to "hkalbert71@gmail.com" \
  --subject "${SUBJECT}"
