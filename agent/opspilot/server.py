"""
The agent's HTTP surface:
  GET  /health                       -- liveness/readiness for Kubernetes
  GET  /metrics                      -- Prometheus scrape target
  POST /webhook/pipeline-failure     -- entry point a CI pipeline calls on failure
  GET  /proposals                    -- list proposals (optionally ?status=pending)
  GET  /proposals/{id}               -- one proposal
  POST /proposals/{id}/approve       -- the human-in-the-loop gate, approve branch
  POST /proposals/{id}/reject        -- the human-in-the-loop gate, reject branch

Approving a proposal does NOT execute it inline in the same request --
it flips the status, and a separate, explicit call to the governance
gate executes it. That extra seam exists on purpose: it's the
difference between "a human can review and the system is merely aware
of their decision" and "approving is actually wired to doing," and
keeping them as two steps makes the audit trail unambiguous about
which happened when.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from opspilot import metrics
from opspilot.config import settings
from opspilot.governance import GovernanceGate, ProposalStatus, ProposalStore
from opspilot.kernel_setup import build_kernel, diagnose_failure
from opspilot.llm_client import build_llm_client
from opspilot.tools.github_tool import GitHubTool
from opspilot.tools.rag_tool import RepoIndex

app = FastAPI(title="OpsPilot", description="Agentic CI/CD diagnosis co-pilot with a human-in-the-loop governance gate")

_repo_index_path = os.environ.get("REPO_INDEX_PATH", ".")
_index = RepoIndex(_repo_index_path)
_kernel = build_kernel(_index)
_llm = build_llm_client(settings)
_github = GitHubTool(settings.github_token, settings.target_repo)
_store = ProposalStore(os.environ.get("OPSPILOT_DB_PATH", "opspilot.db"))
_gate = GovernanceGate(_store)

_gate.register("post_comment", lambda payload: _github.post_comment(payload["issue_number"], payload["body"]))


class PipelineFailurePayload(BaseModel):
    failure_message: str
    issue_number: int | None = None  # the PR/issue to propose commenting on, if known


class DecisionPayload(BaseModel):
    decided_by: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook/pipeline-failure")
async def pipeline_failure(payload: PipelineFailurePayload) -> dict[str, Any]:
    start = time.monotonic()
    diagnosis, prompt_tokens, completion_tokens = await diagnose_failure(_kernel, _llm, payload.failure_message)
    metrics.diagnosis_latency_seconds.observe(time.monotonic() - start)
    metrics.llm_tokens_total.labels(provider=_llm.provider_name, kind="prompt").inc(prompt_tokens)
    metrics.llm_tokens_total.labels(provider=_llm.provider_name, kind="completion").inc(completion_tokens)

    proposal_kind = "post_comment" if payload.issue_number is not None else "diagnosis_only"
    proposal_payload = (
        {"issue_number": payload.issue_number, "body": diagnosis} if payload.issue_number is not None else {}
    )
    proposal = _store.create_pending(
        kind=proposal_kind,
        payload=proposal_payload,
        diagnosis=diagnosis,
        llm_provider=_llm.provider_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    metrics.proposals_created_total.labels(kind=proposal_kind).inc()
    return {"proposal_id": proposal.id, "status": proposal.status.value, "diagnosis": proposal.diagnosis}


@app.get("/proposals")
def list_proposals(status: str | None = None) -> dict[str, Any]:
    status_enum = ProposalStatus(status) if status else None
    return {"proposals": [p.__dict__ for p in _store.list(status_enum)]}


@app.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int) -> dict[str, Any]:
    proposal = _store.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal")
    return proposal.__dict__


@app.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int, decision: DecisionPayload) -> dict[str, Any]:
    try:
        proposal = _store.decide(proposal_id, approve=True, decided_by=decision.decided_by)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    metrics.proposals_decided_total.labels(decision="approved").inc()
    return proposal.__dict__


@app.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, decision: DecisionPayload) -> dict[str, Any]:
    try:
        proposal = _store.decide(proposal_id, approve=False, decided_by=decision.decided_by)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    metrics.proposals_decided_total.labels(decision="rejected").inc()
    return proposal.__dict__


@app.post("/proposals/{proposal_id}/execute")
def execute_proposal(proposal_id: int) -> dict[str, Any]:
    """Runs the gated action for an APPROVED proposal. Refuses (see
    governance.py) for anything not already approved by a human."""
    try:
        result = _gate.execute(proposal_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    proposal_kind = _store.get(proposal_id).kind
    metrics.proposals_executed_total.labels(kind=proposal_kind).inc()
    return {"executed": True, "proposal_id": proposal_id, "result": result}
