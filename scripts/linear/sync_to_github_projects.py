#!/usr/bin/env python3
"""Sync Linear issue states to GitHub Issues + GitHub Projects (v2).

Linear is treated as source-of-truth. This script:
1) Reads Linear issues for a team
2) Ensures mirrored GitHub issues exist (label: linear-id:<IDENTIFIER>)
3) Adds each issue to a GitHub Project v2
4) Updates the Project Status field based on Linear state mapping

Usage:
  python3 scripts/linear/sync_to_github_projects.py

Required env vars:
  LINEAR_API_KEY
  GITHUB_TOKEN
  GITHUB_OWNER
  GITHUB_REPO
  GITHUB_PROJECT_ID      # Project v2 node id, e.g. PVT_xxx

Optional env vars:
  LINEAR_TEAM_KEY=KORA
  LINEAR_MAX_ISSUES=100
  LINEAR_ONLY_KEYS=KORA-14,KORA-18
  DRY_RUN=1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

LINEAR_API_URL = "https://api.linear.app/graphql"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_REST_BASE = "https://api.github.com"


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


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(f"Missing {name}.")


def linear_gql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
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


def github_rest(
    token: str,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{GITHUB_REST_BASE}{path}"
    if query:
        url = f"{url}?{parse.urlencode(query, doseq=True)}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub REST error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub REST connection error: {exc}") from exc
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("GitHub REST response was not a JSON object")
    return parsed


def github_gql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = request.Request(
        GITHUB_GRAPHQL_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub GraphQL connection error: {exc}") from exc
    parsed = json.loads(raw)
    if parsed.get("errors"):
        raise RuntimeError(f"GitHub GraphQL response errors: {parsed['errors']}")
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GitHub GraphQL response missing data")
    return data


def linear_team_id(api_key: str, team_key: str) -> str:
    query = """
    query Teams {
      teams(first: 200) {
        nodes { id key name }
      }
    }
    """
    data = linear_gql(api_key, query)
    teams = data.get("teams", {}).get("nodes", [])
    for t in teams if isinstance(teams, list) else []:
        if not isinstance(t, dict):
            continue
        if str(t.get("key", "")).upper() == team_key.upper():
            return str(t["id"])
    raise RuntimeError(f"Linear team not found by key: {team_key}")


def fetch_linear_issues(api_key: str, team_id: str, max_issues: int, only_keys: set[str]) -> list[dict[str, Any]]:
    query = """
    query TeamIssues($teamId: String!, $first: Int!, $after: String) {
      team(id: $teamId) {
        issues(first: $first, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            identifier
            title
            description
            url
            priority
            state { id name type }
            assignee { id name email }
          }
        }
      }
    }
    """
    out: list[dict[str, Any]] = []
    after: str | None = None
    remaining = max_issues
    while remaining > 0:
        batch = min(remaining, 100)
        data = linear_gql(api_key, query, {"teamId": team_id, "first": batch, "after": after})
        issues = data.get("team", {}).get("issues", {})
        nodes = issues.get("nodes", [])
        if not isinstance(nodes, list):
            break
        for n in nodes:
            if not isinstance(n, dict):
                continue
            ident = str(n.get("identifier", "")).strip()
            if not ident:
                continue
            if only_keys and ident not in only_keys:
                continue
            out.append(n)
        page_info = issues.get("pageInfo", {})
        if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not isinstance(after, str) or not after:
            break
        remaining = max_issues - len(out)
    return out


def map_linear_state_to_github(linear_state_name: str, linear_state_type: str) -> str | None:
    name = linear_state_name.strip().lower()
    state_type = linear_state_type.strip().lower()

    if state_type == "completed" or name in {"done", "completed", "complete"}:
        return "Done"
    if "review" in name:
        return "In Review"
    if "progress" in name or name in {"started", "doing"}:
        return "In Progress"
    if name in {"backlog", "todo", "to do", "triage"}:
        return "Todo"
    return None


def find_or_create_github_issue(
    token: str,
    owner: str,
    repo: str,
    *,
    linear_identifier: str,
    linear_title: str,
    linear_url: str,
    linear_description: str,
    dry_run: bool,
) -> tuple[str, int, str]:
    label = f"linear-id:{linear_identifier}"
    search_q = f'repo:{owner}/{repo} is:issue label:"{label}"'
    search = github_rest(
        token,
        "GET",
        "/search/issues",
        query={"q": search_q, "per_page": 10},
    )
    items = search.get("items", [])
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("pull_request") is not None:
                continue
            num = int(item.get("number", 0))
            if num <= 0:
                continue
            issue = github_rest(token, "GET", f"/repos/{owner}/{repo}/issues/{num}")
            node_id = str(issue.get("node_id", ""))
            html_url = str(issue.get("html_url", ""))
            if node_id:
                return node_id, num, html_url

    title = f"[{linear_identifier}] {linear_title}"
    body_lines = [
        f"Mirrored from Linear: {linear_url}",
        "",
        "_Managed by scripts/linear/sync_to_github_projects.py_",
    ]
    desc = (linear_description or "").strip()
    if desc:
        body_lines.extend(["", "Linear summary:", desc[:1500]])
    body = "\n".join(body_lines)
    labels = ["linear-sync", label]

    if dry_run:
        return "", -1, ""

    created = github_rest(
        token,
        "POST",
        f"/repos/{owner}/{repo}/issues",
        body={"title": title, "body": body, "labels": labels},
    )
    node_id = str(created.get("node_id", ""))
    number = int(created.get("number", 0))
    html_url = str(created.get("html_url", ""))
    if not node_id or number <= 0:
        raise RuntimeError(f"Failed to create mirrored issue for {linear_identifier}")
    return node_id, number, html_url


def get_project_status_field(token: str, project_id: str) -> tuple[str, dict[str, str]]:
    query = """
    query ProjectFields($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
      }
    }
    """
    data = github_gql(token, query, {"projectId": project_id})
    node = data.get("node")
    if not isinstance(node, dict):
        raise RuntimeError("GitHub Project not found")
    fields = node.get("fields", {}).get("nodes", [])
    if not isinstance(fields, list):
        raise RuntimeError("GitHub Project fields missing")
    for field in fields:
        if not isinstance(field, dict):
            continue
        if str(field.get("name", "")).strip().lower() != "status":
            continue
        fid = str(field.get("id", ""))
        options = field.get("options", [])
        if not fid or not isinstance(options, list):
            continue
        mapping: dict[str, str] = {}
        for opt in options:
            if not isinstance(opt, dict):
                continue
            oname = str(opt.get("name", "")).strip()
            oid = str(opt.get("id", "")).strip()
            if oname and oid:
                mapping[oname] = oid
        if mapping:
            return fid, mapping
    raise RuntimeError("Status field not found in GitHub Project")


def get_or_create_project_item(token: str, project_id: str, content_id: str, dry_run: bool) -> str:
    query = """
    query ProjectItems($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              content {
                ... on Issue { id }
              }
            }
          }
        }
      }
    }
    """
    after: str | None = None
    while True:
        data = github_gql(token, query, {"projectId": project_id, "after": after})
        node = data.get("node", {})
        items = node.get("items", {}) if isinstance(node, dict) else {}
        nodes = items.get("nodes", []) if isinstance(items, dict) else []
        for item in nodes if isinstance(nodes, list) else []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, dict) and str(content.get("id", "")) == content_id:
                iid = str(item.get("id", ""))
                if iid:
                    return iid
        page = items.get("pageInfo", {}) if isinstance(items, dict) else {}
        if not isinstance(page, dict) or not page.get("hasNextPage"):
            break
        next_cursor = page.get("endCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            break
        after = next_cursor

    if dry_run:
        return ""

    mutation = """
    mutation AddProjectItem($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
        item { id }
      }
    }
    """
    data = github_gql(token, mutation, {"projectId": project_id, "contentId": content_id})
    item = data.get("addProjectV2ItemById", {}).get("item", {})
    iid = str(item.get("id", ""))
    if not iid:
        raise RuntimeError("Failed to add issue to GitHub Project")
    return iid


def choose_status_option(option_ids: dict[str, str], desired_name: str) -> tuple[str, str]:
    # exact
    if desired_name in option_ids:
        return desired_name, option_ids[desired_name]

    lowered = {k.lower(): (k, v) for k, v in option_ids.items()}
    if desired_name.lower() in lowered:
        return lowered[desired_name.lower()]

    # closest
    if desired_name == "In Progress":
        for cand in ("In progress", "In-Progress", "Doing"):
            if cand in option_ids:
                return cand, option_ids[cand]
    if desired_name == "In Review":
        for k, v in option_ids.items():
            if "review" in k.lower():
                return k, v
    if desired_name == "Done":
        for cand in ("Done", "Completed", "Complete"):
            if cand in option_ids:
                return cand, option_ids[cand]
    if desired_name == "Todo":
        for cand in ("Todo", "To do", "Backlog"):
            if cand in option_ids:
                return cand, option_ids[cand]
    raise RuntimeError(f"No matching GitHub Status option for '{desired_name}'")


def set_project_status(
    token: str,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    mutation = """
    mutation UpdateStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }
      ) {
        projectV2Item { id }
      }
    }
    """
    github_gql(
        token,
        mutation,
        {"projectId": project_id, "itemId": item_id, "fieldId": field_id, "optionId": option_id},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Linear issue states to GitHub Project status")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not create/update GitHub")
    parser.add_argument("--only-keys", default="", help="Comma-separated Linear keys, e.g. KORA-14,KORA-18")
    parser.add_argument("--max-issues", type=int, default=0, help="Override LINEAR_MAX_ISSUES")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    load_env(repo_root)

    linear_api_key = require_env("LINEAR_API_KEY")
    github_token = require_env("GITHUB_TOKEN")
    github_owner = require_env("GITHUB_OWNER")
    github_repo = require_env("GITHUB_REPO")
    github_project_id = require_env("GITHUB_PROJECT_ID")

    linear_team_key = os.getenv("LINEAR_TEAM_KEY", "KORA").strip() or "KORA"
    linear_max_issues = args.max_issues if args.max_issues > 0 else int(os.getenv("LINEAR_MAX_ISSUES", "100"))
    only_keys_raw = args.only_keys.strip() or os.getenv("LINEAR_ONLY_KEYS", "").strip()
    only_keys = {k.strip() for k in only_keys_raw.split(",") if k.strip()} if only_keys_raw else set()
    dry_run = args.dry_run or os.getenv("DRY_RUN", "").strip() == "1"

    team_id = linear_team_id(linear_api_key, linear_team_key)
    issues = fetch_linear_issues(linear_api_key, team_id, linear_max_issues, only_keys)
    if not issues:
        print("No Linear issues found for sync.")
        return 0

    status_field_id, status_options = get_project_status_field(github_token, github_project_id)

    synced = 0
    skipped = 0
    for issue in issues:
        ident = str(issue.get("identifier", "")).strip()
        if not ident:
            continue
        state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
        linear_state_name = str((state or {}).get("name") or "")
        linear_state_type = str((state or {}).get("type") or "")
        gh_target = map_linear_state_to_github(linear_state_name, linear_state_type)
        if not gh_target:
            skipped += 1
            continue

        chosen_name, option_id = choose_status_option(status_options, gh_target)
        node_id, issue_number, issue_url = find_or_create_github_issue(
            github_token,
            github_owner,
            github_repo,
            linear_identifier=ident,
            linear_title=str(issue.get("title") or ident),
            linear_url=str(issue.get("url") or ""),
            linear_description=str(issue.get("description") or ""),
            dry_run=dry_run,
        )
        if dry_run:
            print(f"[DRY] {ident}: {linear_state_name} -> {chosen_name}")
            synced += 1
            continue
        if not node_id:
            raise RuntimeError(f"Missing GitHub issue node_id for {ident}")

        item_id = get_or_create_project_item(github_token, github_project_id, node_id, dry_run=False)
        set_project_status(
            github_token,
            github_project_id,
            item_id,
            status_field_id,
            option_id,
            dry_run=False,
        )
        print(f"{ident} -> {chosen_name} | GH#{issue_number} | {issue_url}")
        synced += 1

    print(f"Sync complete: synced={synced}, skipped={skipped}, dry_run={dry_run}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
