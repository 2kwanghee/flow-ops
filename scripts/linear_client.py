#!/usr/bin/env python3
"""Linear GraphQL API 공용 클라이언트.

모든 linear_*.py 스크립트가 이 모듈을 import하여 사용한다.
"""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

LINEAR_API_URL = "https://api.linear.app/graphql"

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")


def get_env():
    """Load LINEAR_API_KEY and LINEAR_TEAM_ID from .env or env vars."""
    api_key = None
    team_id = None

    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k == "LINEAR_API_KEY":
                    api_key = v
                elif k == "LINEAR_TEAM_ID":
                    team_id = v

    if not api_key:
        api_key = os.getenv("LINEAR_API_KEY")
    if not team_id:
        team_id = os.getenv("LINEAR_TEAM_ID")

    if not api_key or not team_id:
        print("Error: LINEAR_API_KEY and LINEAR_TEAM_ID required.", file=sys.stderr)
        sys.exit(1)

    return api_key, team_id


def linear_request(api_key: str, query: str, variables: dict | None = None):
    """Make a GraphQL request to the Linear API."""
    body = {"query": query}
    if variables:
        body["variables"] = variables

    data = json.dumps(body).encode("utf-8")
    req = Request(LINEAR_API_URL, data=data, method="POST")
    req.add_header("Authorization", api_key)
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode()
        print(f"Linear API Error ({e.code}): {err_body}", file=sys.stderr)
        return None

    if "errors" in result:
        for err in result["errors"]:
            print(f"Linear GraphQL Error: {err.get('message', err)}", file=sys.stderr)
        return None

    return result.get("data")


# ── Workflow State 캐시 ──

_state_cache: dict[str, list[dict]] = {}


def get_workflow_states(api_key: str, team_id: str) -> list[dict]:
    """Get all workflow states for a team (cached)."""
    if team_id in _state_cache:
        return _state_cache[team_id]

    query = """
    query($teamId: String!) {
        team(id: $teamId) {
            states { nodes { id name type } }
        }
    }
    """
    data = linear_request(api_key, query, {"teamId": team_id})
    if not data or not data.get("team"):
        print("Error: 팀 정보를 가져올 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    states = data["team"]["states"]["nodes"]
    _state_cache[team_id] = states
    return states


def find_state_id(api_key: str, team_id: str, state_name: str) -> str | None:
    """Find workflow state ID by name."""
    states = get_workflow_states(api_key, team_id)
    for s in states:
        if s["name"] == state_name:
            return s["id"]
    return None


# ── Priority 매핑 ──
# Linear: 0=None, 1=Urgent, 2=High, 3=Medium, 4=Low
# 프로젝트: P1(긴급), P2(일반), P3(낮음)

PRIORITY_TO_LINEAR = {"P1": 1, "P2": 3, "P3": 4}
PRIORITY_FROM_LINEAR = {0: "P2", 1: "P1", 2: "P1", 3: "P2", 4: "P3"}


def to_linear_priority(p: str) -> int:
    return PRIORITY_TO_LINEAR.get(p, 3)


def from_linear_priority(p: int) -> str:
    return PRIORITY_FROM_LINEAR.get(p, "P2")
