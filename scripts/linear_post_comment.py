#!/usr/bin/env python3
"""Post an end-of-day Linear comment for KORA progress."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error, request

LINEAR_API_URL = "https://api.linear.app/graphql"
PROJECT_NAME = "KORA v1 Runtime"

COMMENT_BODY = """EOD update (2026-02-17)

Studio commits:
- e0b55f1 scaffold
- 52da77d SSE demo trace
- 4d73862 real run_graph via POST+SSE
- 07fd813 backend deps fix
- 97dd4f1 stage metrics overlay
- 4b32212 skip routing visualization
- 12e59de direct vs kora comparison view

Status:
- Studio demo is now a real execution viewer with SSE + metrics + skip path + compare view.

Next:
- Polish UX
- Verify backend deps reproducible in clean env
- Demo prep
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
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def require_linear_key() -> str:
    key = os.getenv("LINEAR_API_KEY", "").strip()
    if key:
        return key
    print("LINEAR_API_KEY is missing.")
    print("Set it with one of the following, then re-run:")
    print("export LINEAR_API_KEY='lin_api_...'")
    print("Or place LINEAR_API_KEY=... in /Users/albertkim/02_PROJECTS/05_KORA/.env")
    raise SystemExit(1)


def gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = request.Request(
        LINEAR_API_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": api_key},
    )
    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Linear HTTP error {exc.code}: {detail}") from exc
    parsed = json.loads(body)
    if parsed.get("errors"):
        raise RuntimeError(f"Linear GraphQL error: {parsed['errors']}")
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Linear response missing data")
    return data


def pick_issue(api_key: str) -> tuple[str, str]:
    query = """
    query ProjectIssues($name: String!) {
      projects(filter: { name: { eq: $name } }, first: 10) {
        nodes {
          id
          name
          issues(first: 100) {
            nodes { id identifier title }
          }
        }
      }
    }
    """
    data = gql(api_key, query, {"name": PROJECT_NAME})
    projects = data.get("projects", {}).get("nodes", [])
    if not projects:
        raise RuntimeError(f"Project not found: {PROJECT_NAME}")
    issues = projects[0].get("issues", {}).get("nodes", [])
    if not issues:
        raise RuntimeError("No issues found in project")

    def issue_num(item: dict) -> int:
        ident = str(item.get("identifier", ""))
        if "-" in ident:
            rhs = ident.split("-")[-1]
            if rhs.isdigit():
                return int(rhs)
        return -1

    target = sorted(issues, key=issue_num, reverse=True)[0]
    return str(target["id"]), str(target.get("identifier", target["id"]))


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
    repo = Path("/Users/albertkim/02_PROJECTS/05_KORA")
    load_dotenv(repo / ".env")
    key = require_linear_key()
    issue_id, identifier = pick_issue(key)
    comment_id = post_comment(key, issue_id, COMMENT_BODY)
    print(f"Linear update posted to {identifier} (comment_id={comment_id})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
