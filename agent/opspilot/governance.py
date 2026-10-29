"""
The actual "governance, guardrails, human-in-the-loop" requirement
from the JD, implemented as code rather than described in a doc: every
action the agent might take is first written to durable storage as a
PENDING proposal. The only way a proposal's underlying tool call ever
executes is through `GovernanceGate.execute()`, and that method
refuses outright unless the proposal's status is APPROVED -- there is
no code path from "the agent decided something" to "the agent did
something" that skips a human decision in between.

Backed by SQLite rather than an in-memory dict: the audit trail (every
proposal, who approved or rejected it, and when) needs to survive a
process restart to be worth anything as an audit trail, and SQLite is
the honest, lightweight way to get that without standing up a second
database just for this.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


@dataclass(frozen=True)
class Proposal:
    id: int
    kind: str
    payload: dict[str, Any]
    diagnosis: str
    status: ProposalStatus
    llm_provider: str
    prompt_tokens: int
    completion_tokens: int
    created_at: float
    decided_at: float | None
    decided_by: str | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    llm_provider TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    created_at REAL NOT NULL,
    decided_at REAL,
    decided_by TEXT
);
"""


class ProposalStore:
    def __init__(self, db_path: str = "opspilot.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def create_pending(
        self, kind: str, payload: dict[str, Any], diagnosis: str,
        llm_provider: str, prompt_tokens: int, completion_tokens: int,
    ) -> Proposal:
        cur = self._conn.execute(
            """INSERT INTO proposals
               (kind, payload, diagnosis, status, llm_provider, prompt_tokens, completion_tokens, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (kind, json.dumps(payload), diagnosis, llm_provider, prompt_tokens, completion_tokens, time.time()),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, proposal_id: int) -> Proposal | None:
        row = self._conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return self._row_to_proposal(row) if row else None

    def list(self, status: ProposalStatus | None = None) -> list[Proposal]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM proposals WHERE status = ? ORDER BY created_at DESC", (status.value,)
            ).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def decide(self, proposal_id: int, approve: bool, decided_by: str) -> Proposal:
        current = self.get(proposal_id)
        if current is None:
            raise KeyError(f"No such proposal: {proposal_id}")
        if current.status != ProposalStatus.PENDING:
            raise ValueError(f"Proposal {proposal_id} is already {current.status.value}, not pending")
        new_status = ProposalStatus.APPROVED if approve else ProposalStatus.REJECTED
        self._conn.execute(
            "UPDATE proposals SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
            (new_status.value, time.time(), decided_by, proposal_id),
        )
        self._conn.commit()
        return self.get(proposal_id)

    def mark_executed(self, proposal_id: int) -> Proposal:
        self._conn.execute("UPDATE proposals SET status = ? WHERE id = ?", (ProposalStatus.EXECUTED.value, proposal_id))
        self._conn.commit()
        return self.get(proposal_id)

    def _row_to_proposal(self, row: tuple) -> Proposal:
        (pid, kind, payload, diagnosis, status, provider, ptoks, ctoks, created, decided_at, decided_by) = row
        return Proposal(
            id=pid, kind=kind, payload=json.loads(payload), diagnosis=diagnosis,
            status=ProposalStatus(status), llm_provider=provider,
            prompt_tokens=ptoks, completion_tokens=ctoks,
            created_at=created, decided_at=decided_at, decided_by=decided_by,
        )


class GovernanceGate:
    """
    The enforcement point. `register(kind, fn)` wires a proposal kind
    to the tool call it's allowed to trigger; `execute()` is the ONLY
    way that call ever runs, and it is a hard failure -- not a warning,
    not a log line -- to call it on anything but an approved proposal.
    """

    def __init__(self, store: ProposalStore):
        self._store = store
        self._actions: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, kind: str, action: Callable[[dict[str, Any]], Any]) -> None:
        self._actions[kind] = action

    def execute(self, proposal_id: int) -> Any:
        proposal = self._store.get(proposal_id)
        if proposal is None:
            raise KeyError(f"No such proposal: {proposal_id}")
        if proposal.status != ProposalStatus.APPROVED:
            raise PermissionError(
                f"Refusing to execute proposal {proposal_id}: status is "
                f"{proposal.status.value!r}, not 'approved'. This is the governance "
                f"gate working as intended, not a bug."
            )
        action = self._actions.get(proposal.kind)
        if action is None:
            raise KeyError(f"No action registered for proposal kind {proposal.kind!r}")
        result = action(proposal.payload)
        self._store.mark_executed(proposal_id)
        return result
