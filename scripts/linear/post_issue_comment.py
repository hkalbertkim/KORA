#!/usr/bin/env python3
"""Post a Linear comment to an issue identifier (e.g., KORA-14).

Usage:
  python3 scripts/linear/post_issue_comment.py --issue KORA-14 --body-file /tmp/msg.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

LINEAR_API_URL = "https://api.linear.app/graphql"


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


def resolve_issue(api_key: str, identifier: str) -> tuple[str, str, str]:
    query = """
    query ResolveIssue($id: String!) {
      issue(id: $id) {
        id
        identifier
        url
      }
    }
    """
    data = gql(api_key, query, {"id": identifier})
    node = data.get("issue")
    if not node:
        raise RuntimeError(f"Issue not found: {identifier}")
    return str(node["id"]), str(node.get("identifier") or identifier), str(node.get("url") or "")


def post_comment(api_key: str, issue_id: str, body: str) -> str:
    mutation = """
    mutation CommentCreate($input: CommentCreateInput!) {
      commentCreate(input: $input) {
        success
        comment { id }
      }
    }
    """
    data = gql(api_key, mutation, {"input": {"issueId": issue_id, "body": body}})
    payload = data.get("commentCreate", {})
    if not payload.get("success"):
        raise RuntimeError("commentCreate failed")
    comment = payload.get("comment") or {}
    return str(comment.get("id", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Post comment to Linear issue identifier")
    parser.add_argument("--issue", required=True, help="Issue identifier, e.g. KORA-14")
    parser.add_argument("--body-file", required=True, help="Path to markdown/text file")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    load_env(repo_root)
    api_key = require_api_key()

    body_path = Path(args.body_file)
    body = body_path.read_text(encoding="utf-8").strip()
    if not body:
        raise RuntimeError("Comment body is empty.")

    issue_id, identifier, url = resolve_issue(api_key, args.issue.strip())
    comment_id = post_comment(api_key, issue_id, body)
    print(f"{identifier}|{comment_id}|{url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
