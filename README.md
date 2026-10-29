# OpsPilot

An agentic CI/CD co-pilot: when a pipeline fails, it retrieves the
relevant parts of the repo, asks an LLM to diagnose the failure, and
proposes a fix — but it can never act on that proposal itself. A
governance gate backed by a durable SQLite audit trail physically
refuses to execute any agent action until a human has approved it.

This exists to close one specific gap: a portfolio project built
entirely on "trust me, it works" infra doesn't demonstrate the thing
a DevOps/Platform/SRE-adjacent, agentic-engineering role actually
needs evidence of. So this repo's CI (`.github/workflows/ci.yml`) is
the point, not an afterthought — on every push, GitHub Actions
creates a real ephemeral Kubernetes cluster (`kind`), runs a real
`terraform apply` that installs a real Helm chart onto it, waits for
the real rollout, and smoke-tests the full proposal lifecycle against
the actually-running service: webhook → ungoverned execute refused
with `403` → human approval → execute allowed. Then it tears the
cluster down. Nothing here is infrastructure-as-code that has never
actually been applied.

## Why this design

| JD requirement | How this repo answers it |
|---|---|
| Agentic AI / LLM orchestration | Real [Semantic Kernel](https://github.com/microsoft/semantic-kernel) plugin + kernel (`agent/opspilot/kernel_setup.py`), not a bare API call |
| Human-in-the-loop governance | `GovernanceGate` (`agent/opspilot/governance.py`) — a `PermissionError`, not a policy doc, is what stops unapproved execution |
| DevOps / Platform / SRE stack | Terraform (`infra/terraform`) orchestrating a Helm chart (`charts/opspilot`) onto Kubernetes, CI'd end-to-end |
| Measuring agent quality, reliability, cost | Prometheus metrics (`agent/opspilot/metrics.py`) + a Grafana dashboard (`monitoring/grafana-dashboard.json`) mapped directly to that language |
| No real production LLM spend in CI | A `Protocol`-based `LLMClient` boundary — tests and CI run against a deterministic `MockLLMClient`; a real provider is opt-in via an explicit env var, never a silent fallback |
| Azure preference, but not yet available to this project | Terraform's `helm` provider is cluster-agnostic; `infra/terraform/main.tf` documents the exact, not-yet-applied path to point it at a real AKS cluster instead of CI's ephemeral `kind` cluster |

## Layout

```
agent/      FastAPI service: webhook → RAG retrieval → SK-orchestrated diagnosis → governed proposal
charts/     Helm chart for the agent (the single source of truth for its Kubernetes manifests)
infra/      Terraform root + module that installs the chart via the helm_release resource
monitoring/ Grafana dashboard + notes on wiring up kube-prometheus-stack for real
.github/    CI: unit tests, Terraform/Helm static validation, and the real end-to-end cluster test
```

## Running it locally

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v                 # 16 tests, all against real SQLite + real TF-IDF retrieval, mocked LLM only
uvicorn opspilot.server:app --reload
```

See `monitoring/README.md` for wiring up real dashboards, and
`infra/terraform/main.tf` for the real-cluster deployment path.
