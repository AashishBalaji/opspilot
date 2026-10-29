import tempfile

import pytest

from opspilot.governance import GovernanceGate, ProposalStatus, ProposalStore


@pytest.fixture
def store():
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    return ProposalStore(db_path)


@pytest.fixture
def gate(store):
    g = GovernanceGate(store)
    calls = []
    g.register("noop", lambda payload: calls.append(payload) or "done")
    g._test_calls = calls  # type: ignore[attr-defined] -- test-only hook
    return g


def test_new_proposal_is_pending(store):
    p = store.create_pending("noop", {}, "diagnosis text", "mock", 10, 5)
    assert p.status == ProposalStatus.PENDING


def test_execute_refuses_a_pending_proposal(store, gate):
    p = store.create_pending("noop", {"x": 1}, "diagnosis", "mock", 10, 5)
    with pytest.raises(PermissionError):
        gate.execute(p.id)
    assert gate._test_calls == []  # the underlying action must never have run


def test_execute_refuses_a_rejected_proposal(store, gate):
    p = store.create_pending("noop", {"x": 1}, "diagnosis", "mock", 10, 5)
    store.decide(p.id, approve=False, decided_by="alice")
    with pytest.raises(PermissionError):
        gate.execute(p.id)
    assert gate._test_calls == []


def test_approve_then_execute_runs_the_action_exactly_once(store, gate):
    p = store.create_pending("noop", {"x": 1}, "diagnosis", "mock", 10, 5)
    store.decide(p.id, approve=True, decided_by="alice")

    result = gate.execute(p.id)

    assert result == "done"
    assert gate._test_calls == [{"x": 1}]
    assert store.get(p.id).status == ProposalStatus.EXECUTED


def test_cannot_decide_an_already_decided_proposal(store):
    p = store.create_pending("noop", {}, "diagnosis", "mock", 10, 5)
    store.decide(p.id, approve=True, decided_by="alice")
    with pytest.raises(ValueError):
        store.decide(p.id, approve=False, decided_by="bob")


def test_list_filters_by_status(store):
    a = store.create_pending("noop", {}, "d1", "mock", 1, 1)
    b = store.create_pending("noop", {}, "d2", "mock", 1, 1)
    store.decide(a.id, approve=True, decided_by="alice")

    pending = store.list(ProposalStatus.PENDING)
    approved = store.list(ProposalStatus.APPROVED)

    assert [p.id for p in pending] == [b.id]
    assert [p.id for p in approved] == [a.id]
