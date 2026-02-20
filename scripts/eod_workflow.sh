#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TODAY="$(date +%F)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "chore: eod workflow sync (${TODAY})"
  git push origin "${BRANCH}"
  echo "[git] committed and pushed changes on ${BRANCH}"
else
  echo "[git] working tree clean; skipping commit/push"
fi

if [[ -n "${LINEAR_API_KEY:-}" ]] || [[ -f ".env" && "$(grep -E '^LINEAR_API_KEY=' .env || true)" != "" ]]; then
  if python3 scripts/linear/update_issue_status.py; then
    COMMENT_BODY="[END][${TODAY}] Adaptive routing (profile + conditional self-consistency + VoI + budget gating) completed. Bench + README updated."
    TMP_COMMENT_FILE="$(mktemp)"
    printf "%s\n" "${COMMENT_BODY}" > "${TMP_COMMENT_FILE}"
    for ISSUE in KORA-14 KORA-15 KORA-16 KORA-17 KORA-18 KORA-19 KORA-20; do
      python3 scripts/linear/post_issue_comment.py --issue "${ISSUE}" --body-file "${TMP_COMMENT_FILE}"
    done
    rm -f "${TMP_COMMENT_FILE}"
    echo "[linear] status/comment update completed"
  else
    echo "[linear] update script failed; continuing to email step"
  fi
else
  echo "[linear] LINEAR_API_KEY not found; skipping Linear update (manual step)"
fi

bash scripts/eod_send_report.sh

echo "[eod] completed"
