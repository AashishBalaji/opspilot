import pytest
import requests

from opspilot.tools.github_tool import GitHubTool


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_get_latest_failed_run_parses_the_response(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert params == {"status": "failure", "per_page": 1}
        return _FakeResponse({"workflow_runs": [{"id": 42, "conclusion": "failure"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    tool = GitHubTool(token="fake-token", repo="octocat/test-repo")

    run = tool.get_latest_failed_run()

    assert run == {"id": 42, "conclusion": "failure"}


def test_get_latest_failed_run_returns_none_when_there_are_no_failures(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"workflow_runs": []}))
    tool = GitHubTool(token="fake-token", repo="octocat/test-repo")

    assert tool.get_latest_failed_run() is None


def test_post_comment_sends_the_body_and_returns_the_created_comment(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse({"id": 1, "body": json["body"]})

    monkeypatch.setattr(requests, "post", fake_post)
    tool = GitHubTool(token="fake-token", repo="octocat/test-repo")

    result = tool.post_comment(7, "proposed fix: bump the timeout")

    assert captured["url"].endswith("/repos/octocat/test-repo/issues/7/comments")
    assert captured["json"] == {"body": "proposed fix: bump the timeout"}
    assert result["body"] == "proposed fix: bump the timeout"


def test_unauthenticated_client_omits_the_authorization_header():
    tool = GitHubTool(token=None, repo="octocat/test-repo")
    assert "Authorization" not in tool._headers
