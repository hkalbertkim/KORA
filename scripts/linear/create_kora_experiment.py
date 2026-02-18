#!/usr/bin/env python3
"""Create KORA experiment parent+child issues in Linear.

Usage:
  python3 scripts/linear/create_kora_experiment.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

LINEAR_API_URL = "https://api.linear.app/graphql"
PARENT_TITLE = "KORA: Long-request Decomposition & Hierarchical Escalation (Experiment)"

TASK_TITLES = [
    "Capture Long PPT request traces (Task IR + DAG)",
    "Measure DAG depth + identify escalation nodes",
    "Classify irreducible LLM nodes vs deterministic candidates",
    "Prototype hierarchical escalation (mini \u2192 full) routing",
    "Benchmark vs baseline (calls, tokens, cost, latency, equivalence)",
    "Write experiment summary + decision (Phase1\u2192Phase2 readiness)",
]


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


def require_api_key() -> str:
    key = os.getenv("LINEAR_API_KEY", "").strip()
    if key:
        return key
    raise RuntimeError("Missing LINEAR_API_KEY.")


def select_team(api_key: str) -> tuple[str, str]:
    team_id = os.getenv("LINEAR_TEAM_ID", "").strip()
    if team_id:
        query = """
        query TeamById($teamId: String!) {
          team(id: $teamId) { id key name }
        }
        """
        data = gql(api_key, query, {"teamId": team_id})
        team = data.get("team")
        if not team:
            raise RuntimeError(f"LINEAR_TEAM_ID not found: {team_id}")
        return str(team["id"]), str(team.get("key") or "")

    query = """
    query Teams {
      teams(first: 100) {
        nodes { id key name }
      }
    }
    """
    data = gql(api_key, query)
    teams = data.get("teams", {}).get("nodes", [])
    if not teams:
        raise RuntimeError("No Linear teams available for this API key.")

    preferred = None
    for t in teams:
        key = str(t.get("key") or "").upper()
        name = str(t.get("name") or "").upper()
        if key == "KORA" or name == "KORA":
            preferred = t
            break
    team = preferred or teams[0]
    return str(team["id"]), str(team.get("key") or "")


def issue_description(task_number: int | None = None) -> str:
    artifact_slug = "parent" if task_number is None else f"task_{task_number:02d}"
    return (
        "## Objective\n"
        "Investigate long-request decomposition and hierarchical escalation behavior in KORA.\n"
        "Document how routing and escalation affect execution quality and efficiency.\n\n"
        "## Success metrics\n"
        "- LLM calls: report baseline vs experiment call count.\n"
        "- tokens_in/out: compare aggregate prompt/completion token volume.\n"
        "- cost delta: quantify absolute and percentage cost changes.\n"
        "- latency: compare p50/p95 end-to-end runtime.\n"
        "- equivalence: validate output quality/parity versus baseline.\n\n"
        "## Output artifacts\n"
        f"- logs/experiments/2026-02-18/{artifact_slug}.jsonl\n"
        f"- docs/reports/experiments/2026-02-18/{artifact_slug}.md\n"
    )


def create_issue(
    api_key: str,
    team_id: str,
    title: str,
    description: str,
    parent_id: str | None = None,
) -> dict[str, str]:
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title url }
      }
    }
    """
    payload: dict[str, Any] = {"teamId": team_id, "title": title, "description": description}
    if parent_id:
        payload["parentId"] = parent_id
    data = gql(api_key, mutation, {"input": payload})
    created = data.get("issueCreate", {})
    if not created.get("success") or not created.get("issue"):
        raise RuntimeError(f"Issue creation failed for title: {title}")
    issue = created["issue"]
    return {
        "id": str(issue["id"]),
        "identifier": str(issue.get("identifier") or issue["id"]),
        "title": str(issue.get("title") or title),
        "url": str(issue.get("url") or ""),
    }


def fallback_url(team_key: str, identifier: str) -> str:
    if team_key:
        return f"https://linear.app/{team_key.lower()}/issue/{identifier}"
    return f"https://linear.app/issue/{identifier}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    load_env(repo_root)

    api_key = require_api_key()
    team_id, team_key = select_team(api_key)

    parent = create_issue(
        api_key=api_key,
        team_id=team_id,
        title=PARENT_TITLE,
        description=issue_description(),
    )
    if not parent["url"]:
        parent["url"] = fallback_url(team_key, parent["identifier"])

    children: list[dict[str, str]] = []
    for idx, title in enumerate(TASK_TITLES, start=1):
        child = create_issue(
            api_key=api_key,
            team_id=team_id,
            title=title,
            description=issue_description(task_number=idx),
            parent_id=parent["id"],
        )
        if not child["url"]:
            child["url"] = fallback_url(team_key, child["identifier"])
        children.append(child)

    print(f"EPIC|{parent['title']}|{parent['identifier']}|{parent['url']}")
    for child in children:
        print(f"TASK|{child['title']}|{child['identifier']}|{child['url']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
