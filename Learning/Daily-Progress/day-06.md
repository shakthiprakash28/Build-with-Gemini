# Day 6: MCP (Model Context Protocol) and Memory Bank


## 🎯 Objectives
- Understand why **MCP** is used to connect the agent to external environments such as a **GKE cluster**.
- Understand **Memory Bank** and how it differs from session memory.
- Configure, deploy and verify both with **agents-cli** on Gemini Enterprise Agent Platform.

## 1. Recap
- Day 3 gave the agent live-cluster **tools** (Kubernetes Python client). Day 4 evaluated it; Day 5 deployed it to Agent Runtime, Cloud Run and GKE.
- Day 1 listed **memory** as a Day-2 operations gap (an agent should remember previous incidents). Day 6 addresses it with **Memory Bank**.

## 2. Part A: MCP 

### What MCP is
An **open-source standard** for connecting AI applications (LLMs/agents) to external systems, tools and data sources. Think of it as a **"universal adapter"**.

### Why it is needed
| Benefit | Explanation |
|---|---|
| **Seamless connectivity** | A common way to talk to external environments (e.g., a GKE cluster) without custom integrations for every tool |
| **Security** | Standardised, controlled two-way connections to private or enterprise systems |
| **Capability** | Agents can "plug in" to tools and fresh data not in the model's training |

### How it relates to what I built
- Day 3 tools = hand-written Python functions calling the Kubernetes client.
- MCP = a **standard interface** exposing such capabilities, so the agent can use a server's tools instead of me writing each one. 

### Production security note 
For production, use an **Internal Load Balancer** and **Private Service Connect (PSC) interfaces** rather than **public IP addresses** to reach the cluster/MCP endpoint. This builds on the Day 5 networking (private VPC, private GKE) and the Day 5 warning about public exposure.

## 3. Part B: Memory Bank

### Session memory vs Memory Bank
| | Session memory | Memory Bank |
|---|---|---|
| Scope | One conversation | **Across sessions** |
| Lifetime | Lost when the session ends | **Persistent / long-term** |
| Example | Remembers what I just said | Remembers a user's preferences or a past incident next week |
| Analogy | Short-term focus | Long-term database |

### Why it matters for the Kubernetes agent
If a config change caused an incident last week and something similar happens later, the agent can use **historical context** instead of investigating from zero (the Day 1 scenario).

# Config from my project


