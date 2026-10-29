"""
The agent's only external write surface, and the one place governance
matters most: everything here that CAN change the target repo
(comment, draft PR) is called only from governance.py's approved path,
never directly from the diagnosis flow. Read operations (fetching a
failed run's logs) are unrestricted -- an agent should be free to look
at anything it needs to diagnose a problem; only acting needs a gate.
"""
from __future__ import annotations

import requests

_API_BASE = "https://api.github.com"


class GitHubTool:
    def __init__(self, token: str | None, repo: str):
        self.repo = repo
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    # --- reads: unrestricted ---

    def get_latest_failed_run(self) -> dict | None:
        resp = requests.get(
            f"{_API_BASE}/repos/{self.repo}/actions/runs",
            params={"status": "failure", "per_page": 1},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        return runs[0] if runs else None

    def get_run_jobs(self, run_id: int) -> list[dict]:
        resp = requests.get(
            f"{_API_BASE}/repos/{self.repo}/actions/runs/{run_id}/jobs",
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    # --- writes: callable only from an approved proposal (see governance.py) ---

    def post_comment(self, issue_or_pr_number: int, body: str) -> dict:
        resp = requests.post(
            f"{_API_BASE}/repos/{self.repo}/issues/{issue_or_pr_number}/comments",
            json={"body": body},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
