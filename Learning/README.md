# Building an Enterprise AI Agent: Gemini Enterprise Agent Platform

A hands-on, project-driven learning log following the **"Building an AI Agent"**. The running project is a **Kubernetes Investigation Agent** that is taken
from prototype to an enterprise-grade, production-style agent.

## Objective
Learn the **complete lifecycle of an enterprise agent**, not just how to build one:

| Phase | Focus | Platform features |
|---|---|---|
| 1. Build | Create the agent | Agent Development Kit (ADK), Agent CLI, Model Garden |
| 2. Deploy & Scale | Run it reliably for many users | Agent Runtime |
| 3. Govern | Identity, access, control | Agent Identity (SPIFFE), Agent Registry, Policies, Gateway |
| 4. Observe | Activity, quality, cost | Google Cloud Observability, Cost Management, Agent Evaluation, Memory Bank |


## Project: Kubernetes Investigation Agent
- **Problem:** SRE/DevOps engineers spend significant time logging into clusters, reading logs/events/deployment
  history and writing investigation reports.
- **Solution:** An agent that takes cluster output as input and returns root cause, supporting evidence,
  impact and remediation.
- **v1 (Day 2):** Input is a log/`kubectl describe` output file. No live cluster access yet.
- **Roadmap:** live cluster access via MCP → evaluation → Agent Runtime → Memory Bank → Agent Identity → governance → observability & cost.

## References
- Docs: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build

> ⚠️ Security: no API keys, service-account JSON, kubeconfig or `.env` files are committed to this repo.
