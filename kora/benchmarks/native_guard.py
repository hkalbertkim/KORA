"""Require a fresh shared lease observation before a native comparison call."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from .worker import WorkerError


def validate_status(status, lease_id, project, unit, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        lease = status["lease"]
        observed = status["observed"]
        age = (now - datetime.fromisoformat(observed["sampled_at"])).total_seconds()
        if not 0 <= age <= 30:
            raise ValueError()
        if (
            lease["lease_id"] != lease_id
            or lease["project"] != project
            or lease["unit"] != unit
            or status["overdue"]
        ):
            raise ValueError()
        if now >= datetime.fromisoformat(lease["expected_end"]):
            raise ValueError()
        if not observed["processes"] or any(
            p["service"] != unit for p in observed["processes"]
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkerError("native-lease-not-current", 409) from exc
    return {
        "lease_id": lease_id,
        "project": project,
        "sampled_at": observed["sampled_at"],
    }


class NativeGuard:
    def __init__(self, command, lease_id, project, unit):
        self.command, self.lease_id, self.project, self.unit = (
            command,
            lease_id,
            project,
            unit,
        )

    def __call__(self):
        try:
            result = subprocess.run(
                self.command, capture_output=True, timeout=10, check=True
            )
            if len(result.stdout) > 65536:
                raise ValueError()
            status = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise WorkerError("native-lease-observation-failed", 409) from exc
        return validate_status(status, self.lease_id, self.project, self.unit)
