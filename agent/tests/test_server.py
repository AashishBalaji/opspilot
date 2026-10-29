"""
The full loop, end to end, through the real HTTP layer: a pipeline
failure comes in -> a real (TF-IDF) retrieval runs against this
project's own code -> a (mocked) LLM produces a diagnosis -> a
proposal is created PENDING -> attempting to execute it before
approval is refused -> approving flips it -> executing it now actually
calls the (monkeypatched) GitHub tool and marks it EXECUTED.

This is the single test that proves the governance gate is wired into
the real request path, not just correct in isolation (test_governance.py
already covers the gate's own logic in isolation).
"""
import requests
from fastapi.testclient import TestClient

from opspilot import server


def test_full_proposal_lifecycle_through_the_api(monkeypatch):
    captured_comment = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_comment["json"] = json

        class _Resp:
            def json(self):
                return {"id": 999, **json}

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    client = TestClient(server.app)

    create_resp = client.post(
        "/webhook/pipeline-failure",
        json={"failure_message": "TypeError in governance.py: expected str, got dict", "issue_number": 7},
    )
    assert create_resp.status_code == 200
    proposal_id = create_resp.json()["proposal_id"]

    pending = client.get("/proposals", params={"status": "pending"})
    assert any(p["id"] == proposal_id for p in pending.json()["proposals"])

    refused = client.post(f"/proposals/{proposal_id}/execute")
    assert refused.status_code == 403  # governance gate refuses an unapproved proposal, even via the real route

    approve_resp = client.post(f"/proposals/{proposal_id}/approve", json={"decided_by": "nishalini"})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    execute_resp = client.post(f"/proposals/{proposal_id}/execute")
    assert execute_resp.status_code == 200
    assert execute_resp.json()["executed"] is True
    assert captured_comment["json"]["body"]  # the diagnosis text was actually posted

    final = client.get(f"/proposals/{proposal_id}")
    assert final.json()["status"] == "executed"


def test_rejecting_a_proposal_permanently_blocks_execution(monkeypatch):
    client = TestClient(server.app)
    create_resp = client.post("/webhook/pipeline-failure", json={"failure_message": "flaky test timeout"})
    proposal_id = create_resp.json()["proposal_id"]

    client.post(f"/proposals/{proposal_id}/reject", json={"decided_by": "nishalini"})

    execute_resp = client.post(f"/proposals/{proposal_id}/execute")
    assert execute_resp.status_code == 403


def test_health_and_metrics_endpoints():
    client = TestClient(server.app)
    assert client.get("/health").json() == {"status": "ok"}
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert b"opspilot_proposals_created_total" in metrics_resp.content
