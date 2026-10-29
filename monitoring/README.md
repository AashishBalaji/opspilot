# Monitoring

The agent exposes real Prometheus-format metrics at `/metrics`
(`opspilot/metrics.py`), updated from the real request path
(`server.py`), not seeded with placeholder values — `GET
http://<service>/metrics` after installing the chart returns genuine
counters that increase as the agent is actually used.

## Wiring it up

This repo's CI deliberately does **not** install a full Prometheus +
Grafana stack on the ephemeral `kind` cluster — that's a slow, heavy
addition to every single CI run for a check that doesn't need it; CI's
smoke test instead curls `/metrics` directly and asserts the expected
metric names are present (see `.github/workflows/ci.yml`). The actual
scrape and dashboard config below is real and meant for a longer-lived
cluster:

1. Install [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) (brings the Prometheus Operator CRDs the chart's `ServiceMonitor` needs):
   ```bash
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
   ```
2. Install OpsPilot with the ServiceMonitor turned on:
   ```bash
   helm install opspilot ../charts/opspilot --set serviceMonitor.enabled=true
   ```
   Prometheus Operator auto-discovers it via label selectors — no manual scrape config needed.
3. Import `grafana-dashboard.json` into Grafana (Dashboards → Import → upload JSON).

## What the dashboard tracks

Directly maps to the JD's "measure efficiency and scalability gains,
and continuously improve agent quality, reliability, and cost":

- **Proposals created** — volume, by kind.
- **Approval vs. rejection rate** — the core quality signal. A healthy agent's acceptance rate stays high and stable; a drop is the earliest warning sign of degrading diagnosis quality.
- **Diagnosis latency (p50/p95)** — reliability/performance.
- **LLM tokens consumed** — the cost signal, split prompt vs. completion, by provider.
- **Proposals executed vs. approved** — a correctness invariant as much as a metric: executed should never exceed approved. If it ever does, that's not a dashboard anomaly, it's a governance-gate failure worth paging on.
