#!/usr/bin/env python3
"""Send KORA daily report email via SMTP env configuration."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

TO_ADDR = "hkalbert71@gmail.com"
SUBJECT = "KORA Daily Report – 2026-02-17"
BODY = """KORA Daily Report – Feb 17, 2026

KORA Core (Infra)
- Runtime boundary spec (KORA-1)
- Structured runtime error contract (KORA-2)
- Production-like benchmark harness + measured results (KORA-3/4)
- Telemetry CLI + JSON + Markdown report (KORA-7/8)
- Cost estimation + savings delta (M4); Long case measured savings ~11.25%
- Stress test harness (M5): 1000 sequential mixed workload; schema mode + budget breach mode validated

KORA Studio (macOS demo)
- Studio scaffold in-repo (e0b55f1)
- SSE streaming for live routing animation (52da77d)
- Real run_graph execution wired via POST+SSE (4d73862)
- Backend deps fixed (07fd813)
- Stage metrics overlay (97dd4f1)
- Skip route visualization (4b32212)
- Direct vs KORA comparison view (12e59de)

Current status
- Studio is now a real Execution Viewer (not a mock): live routing + metrics + skip visualization + comparison.

Next
- UX polish + demo reliability pass
- Optional: adapter toggle (mock/openai/ollama) and richer cost overlay
"""


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k and k not in os.environ:
            os.environ[k] = v


def require_smtp_env() -> dict[str, str]:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"]
    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print("Missing SMTP environment variables:")
        for k in missing:
            print(f"- {k}")
        print("Set them and re-run. Example:")
        print("export SMTP_HOST='smtp.example.com'")
        print("export SMTP_PORT='587'")
        print("export SMTP_USER='your_username'")
        print("export SMTP_PASS='your_password'")
        print("export SMTP_FROM='you@example.com'")
        raise SystemExit(1)
    return {k: os.getenv(k, "").strip() for k in required}


def send_email(cfg: dict[str, str]) -> None:
    msg = EmailMessage()
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = TO_ADDR
    msg["Subject"] = SUBJECT
    msg.set_content(BODY)

    port = int(cfg["SMTP_PORT"])
    if port == 465:
        with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            smtp.send_message(msg)
        return

    with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
        smtp.send_message(msg)


def main() -> int:
    load_dotenv(Path("/Users/albertkim/02_PROJECTS/05_KORA/.env"))
    cfg = require_smtp_env()
    try:
        send_email(cfg)
    except smtplib.SMTPException as exc:
        print(f"SMTP error: {exc}")
        return 1
    except OSError as exc:
        print(f"SMTP error: {exc}")
        return 1

    print("Email sent to hkalbert71@gmail.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
