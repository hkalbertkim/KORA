#!/usr/bin/env python3
"""Send a markdown daily report as plain text email via SMTP."""

from __future__ import annotations

import argparse
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path


NBSP = "\u00a0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv(env_path)
        return

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _check_nbsp(field_name: str, value: str) -> None:
    if NBSP in value:
        raise RuntimeError(
            f"Invalid {field_name}: contains non-breaking space (U+00A0). "
            "Re-enter the value using normal spaces."
        )


def load_smtp_config() -> dict[str, str]:
    host = _require_env("SMTP_HOST")
    port = _require_env("SMTP_PORT")
    user = _require_env("SMTP_USER")
    password = _require_env("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", "").strip() or user

    _check_nbsp("SMTP_USER", user)
    _check_nbsp("SMTP_PASS", password)
    _check_nbsp("SMTP_FROM", from_addr)

    return {
        "SMTP_HOST": host,
        "SMTP_PORT": port,
        "SMTP_USER": user,
        "SMTP_PASS": password,
        "SMTP_FROM": from_addr,
    }


def send_email(*, cfg: dict[str, str], to_addr: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        port = int(cfg["SMTP_PORT"])
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer") from exc

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send markdown daily report via SMTP")
    parser.add_argument("--report", required=True, help="Path to markdown report file")
    parser.add_argument("--to", default="hkalbert71@gmail.com", help="Recipient email address")
    parser.add_argument(
        "--subject",
        default=f"KORA Daily Report - {date.today().isoformat()}",
        help="Email subject",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = Path(args.report)

    if not report_path.exists() or not report_path.is_file():
        print(f"Error: report file not found: {report_path}")
        return 1

    try:
        body = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: failed to read report file: {exc}")
        return 1

    load_env(_repo_root())

    try:
        cfg = load_smtp_config()
        send_email(cfg=cfg, to_addr=args.to, subject=args.subject, body=body)
    except (RuntimeError, smtplib.SMTPException, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Email sent: to={args.to} subject={args.subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
