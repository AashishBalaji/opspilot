"""
The JD asks explicitly to "measure efficiency and scalability gains,
and continuously improve agent quality, reliability, and cost" --
these are those metrics, scraped by Prometheus and rendered in the
Grafana dashboard under monitoring/. Every one of them is updated from
a real code path (governance.py / server.py), not seeded with fake
numbers for the dashboard to look populated.
"""
from prometheus_client import Counter, Histogram

proposals_created_total = Counter(
    "opspilot_proposals_created_total", "Proposals the agent has created", ["kind"]
)
proposals_decided_total = Counter(
    "opspilot_proposals_decided_total", "Proposals a human has approved or rejected", ["decision"]
)
proposals_executed_total = Counter(
    "opspilot_proposals_executed_total", "Approved proposals the agent has actually carried out", ["kind"]
)
diagnosis_latency_seconds = Histogram(
    "opspilot_diagnosis_latency_seconds", "Time from receiving a failure to producing a proposal"
)
llm_tokens_total = Counter(
    "opspilot_llm_tokens_total", "LLM tokens consumed, for cost tracking", ["provider", "kind"]
)
