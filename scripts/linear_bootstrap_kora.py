#!/usr/bin/env python3
"""Bootstrap a Linear Kanban setup for the KORA repository.

Creates (or reuses):
- Team (prefers key KORA)
- Project: KORA v1 Runtime
- Labels
- Initial issues grouped by milestones
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


LINEAR_API_URL = "https://api.linear.app/graphql"
PROJECT_NAME = "KORA v1 Runtime"
LABELS = [
    "runtime",
    "ir",
    "scheduler",
    "budgets",
    "telemetry",
    "benchmarks",
    "stress-test",
    "docs",
]
MILESTONES = [
    {
        "code": "M1",
        "name": "Runtime Hardening",
        "items": [
            ("Define runtime boundaries", ["runtime", "docs"]),
            ("Codify error taxonomy", ["runtime", "docs"]),
            ("Implement task registry invariants", ["runtime", "ir"]),
        ],
    },
    {
        "code": "M2",
        "name": "Real Workload Integration",
        "items": [
            ("Select first production-like app", ["runtime", "benchmarks"]),
            ("Route workload via KORA", ["runtime", "scheduler"]),
            ("Publish benchmark methodology doc", ["benchmarks", "docs"]),
        ],
    },
    {
        "code": "M3",
        "name": "Telemetry Surface",
        "items": [
            ("Ship CLI + JSON telemetry export", ["telemetry", "runtime"]),
            ("Add report template for runtime summaries", ["telemetry", "docs"]),
        ],
    },
    {
        "code": "M4",
        "name": "Cost Model Validation",
        "items": [
            ("Map token usage to cost model", ["budgets", "telemetry"]),
            ("Implement cost estimator workflow", ["budgets", "runtime"]),
        ],
    },
    {
        "code": "M5",
        "name": "Stress Testing",
        "items": [
            ("Run 1000-request simulation harness", ["stress-test", "benchmarks"]),
            ("Validate mixed-workload behavior", ["stress-test", "scheduler"]),
            ("Verify budget-exhaustion behavior", ["stress-test", "budgets"]),
        ],
    },
]


class LinearClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def gql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        req = request.Request(
            LINEAR_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Linear API HTTP error {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Linear API connection error: {exc}") from exc

        parsed = json.loads(raw)
        if parsed.get("errors"):
            raise RuntimeError(f"Linear GraphQL error: {parsed['errors']}")
        data = parsed.get("data")
        if data is None:
            raise RuntimeError("Linear API returned empty data payload.")
        return data


def load_dotenv(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def require_api_key() -> str:
    key = os.environ.get("LINEAR_API_KEY", "").strip()
    if key:
        return key
    print("LINEAR_API_KEY is missing.")
    print("Create one in Linear UI:")
    print("1) Open Linear.")
    print("2) Go to Settings > Security & access > Personal API keys.")
    print("3) Click 'Create key', copy it, and export LINEAR_API_KEY.")
    print("   Example: export LINEAR_API_KEY='lin_api_...'")
    sys.exit(1)


def viewer_and_teams(client: LinearClient) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    query = """
    query ViewerTeams {
      viewer { id name email }
      teams(first: 100) {
        nodes { id key name }
      }
    }
    """
    data = client.gql(query)
    return data["viewer"], data["teams"]["nodes"]


def get_team_by_key(teams: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    key_upper = key.upper()
    for t in teams:
        if (t.get("key") or "").upper() == key_upper:
            return t
    return None


def try_create_team(client: LinearClient, name: str, key: str) -> dict[str, Any] | None:
    mutation = """
    mutation TeamCreate($input: TeamCreateInput!) {
      teamCreate(input: $input) {
        success
        team { id key name }
      }
    }
    """
    try:
        data = client.gql(mutation, {"input": {"name": name, "key": key}})
    except RuntimeError:
        return None
    payload = data.get("teamCreate") or {}
    if not payload.get("success"):
        return None
    return payload.get("team")


def pick_or_create_team(client: LinearClient, teams: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    existing_kora = get_team_by_key(teams, "KORA")
    if existing_kora:
        return existing_kora, "existing_kora_team"

    created = try_create_team(client, "KORA", "KORA")
    if created:
        return created, "new_team_created"

    if teams:
        return teams[0], "fallback_existing_team"
    raise RuntimeError("No accessible team found and team creation failed.")


def get_or_create_project(client: LinearClient, team_id: str) -> tuple[dict[str, Any], bool]:
    query = """
    query ProjectsList {
      projects(first: 100) {
        nodes { id name }
      }
    }
    """
    data = client.gql(query)
    existing = next((p for p in data["projects"]["nodes"] if p.get("name") == PROJECT_NAME), None)
    if existing:
        return existing, False

    mutation = """
    mutation CreateProject($input: ProjectCreateInput!) {
      projectCreate(input: $input) {
        success
        project { id name }
      }
    }
    """
    created = client.gql(
        mutation,
        {"input": {"name": PROJECT_NAME, "teamIds": [team_id], "description": "KORA runtime execution roadmap."}},
    )["projectCreate"]
    if not created.get("success") or not created.get("project"):
        raise RuntimeError("Failed to create project.")
    return created["project"], True


def fetch_team_labels(client: LinearClient, team_id: str) -> dict[str, dict[str, Any]]:
    query = """
    query TeamLabels($teamId: ID!) {
      issueLabels(first: 200, filter: { team: { id: { eq: $teamId } } }) {
        nodes { id name }
      }
    }
    """
    data = client.gql(query, {"teamId": team_id})
    labels = {}
    for label in data["issueLabels"]["nodes"]:
        labels[label["name"].strip().lower()] = label
    return labels


def ensure_labels(client: LinearClient, team_id: str) -> dict[str, str]:
    existing = fetch_team_labels(client, team_id)
    out: dict[str, str] = {}
    mutation = """
    mutation CreateLabel($input: IssueLabelCreateInput!) {
      issueLabelCreate(input: $input) {
        success
        issueLabel { id name }
      }
    }
    """
    for name in LABELS:
        key = name.lower()
        if key in existing:
            out[name] = existing[key]["id"]
            continue
        created = client.gql(mutation, {"input": {"name": name, "teamId": team_id}})["issueLabelCreate"]
        if created.get("success") and created.get("issueLabel"):
            out[name] = created["issueLabel"]["id"]
        else:
            raise RuntimeError(f"Failed to create label '{name}'.")
    return out


def create_issues(
    client: LinearClient,
    team_id: str,
    project_id: str,
    label_ids: dict[str, str],
) -> list[dict[str, str]]:
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title }
      }
    }
    """
    created: list[dict[str, str]] = []
    for milestone in MILESTONES:
        milestone_header = f"{milestone['code']} {milestone['name']}"
        for title, labels in milestone["items"]:
            full_title = f"[{milestone['code']}] {title}"
            description = (
                f"## Milestone\n{milestone_header}\n\n"
                f"## Objective\n{title}\n\n"
                "## Done When\n- Scope is implemented.\n- Behavior is documented.\n- Validation evidence is attached."
            )
            issue_label_ids = [label_ids[l] for l in labels if l in label_ids]
            payload = {
                "teamId": team_id,
                "projectId": project_id,
                "title": full_title,
                "description": description,
                "labelIds": issue_label_ids,
            }
            result = client.gql(mutation, {"input": payload})["issueCreate"]
            if result.get("success") and result.get("issue"):
                created.append(result["issue"])
            else:
                raise RuntimeError(f"Failed to create issue '{full_title}'.")
    return created


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root)
    api_key = require_api_key()
    client = LinearClient(api_key)

    viewer, teams = viewer_and_teams(client)
    team, team_mode = pick_or_create_team(client, teams)
    project, created_project = get_or_create_project(client, team["id"])
    label_ids = ensure_labels(client, team["id"])
    issues = create_issues(client, team["id"], project["id"], label_ids)

    print("Linear bootstrap complete.")
    print(f"Viewer: {viewer.get('name') or viewer.get('email')}")
    print(f"Team mode: {team_mode}")
    print(f"Team: id={team['id']}, key={team['key']}, name={team['name']}")
    print(f"Project: id={project['id']}, name={project['name']} ({'created' if created_project else 'reused'})")
    print("Issues:")
    for issue in issues:
        print(f"- {issue.get('identifier', issue['id'])} | {issue['id']} | {issue['title']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
