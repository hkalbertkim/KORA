#!/usr/bin/env python3
"""Update Linear issue statuses for today's KORA workflow sync.

Usage:
  python3 scripts/linear/update_issue_status.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

LINEAR_API_URL = "https://api.linear.app/graphql"

TARGETS: dict[str, str] = {
    "KORA-14": "In Progress",
    "KORA-18": "In Review",
    "KORA-19": "In Review",
    "KORA-20": "In Progress",
    "KORA-15": "Done",
    "KORA-16": "Done",
    "KORA-17": "Done",
}


def load_env(repo_root: Path) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        load_dotenv = None

    env_path = repo_root / ".env"
    if load_dotenv:
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
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def require_api_key() -> str:
    key = os.getenv("LINEAR_API_KEY", "").strip()
    if key:
        return key
    raise RuntimeError("Missing LINEAR_API_KEY.")


def gql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = request.Request(
        LINEAR_API_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": api_key},
    )
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Linear HTTP error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Linear connection error: {exc}") from exc

    parsed = json.loads(raw)
    if parsed.get("errors"):
        raise RuntimeError(f"Linear GraphQL error: {parsed['errors']}")
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Linear GraphQL response missing data")
    return data


def get_issue(api_key: str, identifier: str) -> dict[str, Any]:
    query = """
    query IssueByIdentifier($id: String!) {
      issue(id: $id) {
        id
        identifier
        url
        state { id name type }
        team { id key name }
      }
    }
    """
    data = gql(api_key, query, {"id": identifier})
    issue = data.get("issue")
    if not isinstance(issue, dict):
        raise RuntimeError(f"Issue not found: {identifier}")
    return issue


def get_team_states(api_key: str, team_id: str) -> list[dict[str, Any]]:
    query = """
    query TeamStates($teamId: String!) {
      team(id: $teamId) {
        id
        states(first: 200) {
          nodes { id name type }
        }
      }
    }
    """
    data = gql(api_key, query, {"teamId": team_id})
    team = data.get("team")
    if not isinstance(team, dict):
        raise RuntimeError(f"Team not found: {team_id}")
    states = team.get("states", {}).get("nodes", [])
    if not isinstance(states, list) or not states:
        raise RuntimeError(f"No states found for team: {team_id}")
    return [s for s in states if isinstance(s, dict)]


def choose_state(states: list[dict[str, Any]], target_name: str) -> tuple[str, str]:
    # 1) exact name match
    for s in states:
        if str(s.get("name", "")).strip().lower() == target_name.lower():
            return str(s["id"]), str(s["name"])

    normalized = target_name.strip().lower()
    # 2) nearest by common naming
    if normalized == "in progress":
        for candidate in ("in progress", "in-progress", "started", "doing"):
            for s in states:
                name = str(s.get("name", "")).strip().lower()
                if candidate in name:
                    return str(s["id"]), str(s["name"])
    if normalized == "in review":
        for s in states:
            name = str(s.get("name", "")).strip().lower()
            if "review" in name:
                return str(s["id"]), str(s["name"])
    if normalized == "done":
        for s in states:
            name = str(s.get("name", "")).strip().lower()
            if name in {"done", "completed", "complete"}:
                return str(s["id"]), str(s["name"])
        for s in states:
            if str(s.get("type", "")).strip().lower() == "completed":
                return str(s["id"]), str(s["name"])

    raise RuntimeError(f"No suitable state found for target '{target_name}'")


def update_issue_state(api_key: str, issue_id: str, state_id: str) -> None:
    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
      }
    }
    """
    data = gql(api_key, mutation, {"id": issue_id, "input": {"stateId": state_id}})
    payload = data.get("issueUpdate", {})
    if not payload.get("success"):
        raise RuntimeError(f"issueUpdate failed for issue id {issue_id}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    load_env(repo_root)
    api_key = require_api_key()

    seed = get_issue(api_key, "KORA-14")
    team = seed.get("team")
    if not isinstance(team, dict) or not team.get("id"):
        raise RuntimeError("Could not auto-discover team from KORA-14")
    team_id = str(team["id"])
    states = get_team_states(api_key, team_id)

    # Resolve all targets first (capture old states/urls)
    resolved: dict[str, dict[str, str]] = {}
    for key in TARGETS:
        issue = get_issue(api_key, key)
        state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
        resolved[key] = {
            "id": str(issue["id"]),
            "url": str(issue.get("url") or ""),
            "old_state": str((state or {}).get("name") or "Unknown"),
        }

    # Perform updates
    applied_state_name: dict[str, str] = {}
    for key, target in TARGETS.items():
        state_id, chosen_name = choose_state(states, target)
        update_issue_state(api_key, resolved[key]["id"], state_id)
        applied_state_name[key] = chosen_name

    # Verify and print confirmations
    for key in TARGETS:
        after = get_issue(api_key, key)
        after_state = after.get("state") if isinstance(after.get("state"), dict) else {}
        after_name = str((after_state or {}).get("name") or "Unknown")
        before_name = resolved[key]["old_state"]
        url = resolved[key]["url"] or str(after.get("url") or "")
        chosen = applied_state_name[key]
        if after_name != chosen:
            raise RuntimeError(f"Verification failed for {key}: expected '{chosen}', got '{after_name}'")
        print(f"{key}: {before_name} -> {after_name} ({url})")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
