# Day 1: Prototype vs Enterprise Agent (Day-1 vs Day-2 Operations)



## 🎯 Objectives
- Understand the series structure and the end-to-end agent lifecycle.
- Understand why a working prototype is not production-ready.
- Map each production gap to a Gemini Enterprise Agent Platform feature.

## 1.  Overview
- Project: **Kubernetes Investigation Agent** for a DevOps/SRE team.
- Built using **Gemini Enterprise Agent Platform** on **Google Cloud Platform (GCP)**.
- Four lifecycle pillars:
  1. **Build** the agent
  2. **Deploy & scale** the agent
  3. **Govern** the agent
  4. **Observe** the deployed agent in production

## 2. Day-1 vs Day-2 operations (core idea)
| | Day-1 operations | Day-2 operations |
|---|---|---|
| Meaning | Getting a working **prototype** | Running it in **production** |
| How | Prompt a coding agent (Claude, Cursor, Copilot…), connect tools/MCP/RAG | Trust, runtime, memory, identity, observability, cost, accountability |
| Example | "What's wrong with my cluster?" → agent reads pods/logs/deployments and answers | Can we trust that answer? Where does it run? Who is it? What can it access? |

**Production questions a prototype can't answer:**
- Can we trust the agent's answers?
- Where will the agent run?
- Can it remember previous incidents?
- Who is the agent, and what is it allowed to access?
- Can we see what it did?
- What does it cost to run?
- Who is accountable for it?

## 3. The six production gaps → platform features

| # | Gap | Why it matters (example from video) | Platform feature |
|---|---|---|---|
| 1 | **Trust** | Agent says "memory issue." Either it found real evidence (logs/events/changes) **or** the model guessed. In production, you can't blindly trust an AI answer. | **Agent Evaluation** |
| 2 | **Runtime / scale** | Many users and simultaneous incidents; who restarts the agent if it crashes? | **Agent Runtime** (production environment for deploying & scaling) |
| 3 | **Memory** | A config change caused an incident last week; a similar one occurs later. Agent shouldn't investigate from zero. | **Memory Bank** (persistent memory beyond a single session) |
| 4 | **Identity** | Investigation agent = read-only; an infra-change agent needs read+write. Every agent needs its own identity and access. | **Agent Identity** + **SPIFFE IDs** |
| 5 | **Observability** | Need a detailed record: what the agent did, when, what failed, success rate. | **Google Cloud Observability** |
| 6 | **Cost** | Prevent runaway model costs; see where infra spend goes. Cheaper models can serve low-thinking tasks. | **Google Cloud Cost Management** + **Model Garden** (Google + third-party models) |

## 4. Key terms introduced
- **Agent Evaluation:** measures whether agent outputs are correct/grounded.
- **Agent Runtime:** managed hosting for deployment and scaling.
- **Memory Bank:** persistent agent memory across sessions.
- **Agent Identity / SPIFFE:** unique, verifiable identity per agent (details in a later video).
- **Model Garden:** catalogue of Google and third-party models to choose per task/cost.

## 💡 Key takeaways
1. Building the agent is the easy part; operating it safely is the real work.
2. "Prototype works" ≠ "production ready." Trust, runtime, memory, identity, observability and cost must be solved.
3. Evaluation is how we replace blind trust with measurable confidence.
4. Least-privilege identity per agent is critical in enterprise settings.
5. Model choice is a cost lever: use cheaper models for simpler tasks.

## ❓ Questions to revisit
- How will evaluation datasets for K8s investigations be built?
- What access will the investigation agent need (read-only scope)?
- Which model tier is appropriate for log analysis vs reasoning?
