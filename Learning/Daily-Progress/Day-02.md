# Day 2: Setup and Build the First Kubernetes Investigation Agent (v1)



## 🎯 Objectives
- Set up Gemini Enterprise Agent Platform on GCP.
- Set up a coding agent and integrate it with **Agent CLI**.
- Generate a Kubernetes Investigation Agent from a natural-language prompt, run it, and validate it.

## 1. Concepts

| Concept | Meaning |
|---|---|
| **AI agent** | Autonomous software that plans and performs multi-step actions to reach a goal (here: investigate a K8s issue). |
| **ADK (Agent Development Kit)** | Open-source Google framework for building, deploying and operating agents. Gives context management, session management, model switching, MCP integration. |
| **Agent CLI** | Component of the platform: a CLI plus a set of agent **skills**. Lets a coding agent invoke ADK so you build agents from natural language. Also supports deploy, evaluation and observability (used in later days). |
| **Skills** | Sets of instructions that tell a coding agent how to perform a task a particular way. |
| **Coding agent** | AI tool (Claude, Antigravity CLI, Copilot, Cursor…) that receives your prompt. The author used **Google Antigravity CLI** (`agy`). |
| **Agent Studio** | UI/no-CLI way to build agents on the platform (not used in this series). |

**Why a framework (ADK) instead of just prompting a coding agent?** Enterprise agents need context and session management, switchable models, and MCP integration.

## 2. Use case
Without an agent: a developer reports "payment service down" → DevOps connects to the cluster, reads logs, checks events, reviews deployment history, finds the cause and writes up evidence. This is **tedious and time-consuming**. The agent automates the investigation.

## 3. Setup steps (what I did)

### Step 1: GCP / Agent Platform account
1. Sign up for the Gemini Enterprise Agent Platform (new users: up to **$300 free credits**).
2. **Create a dedicated project** (e.g. `Kubernetes investigation agent`) rather than using the default project. Benefit: all agent resources stay together and billing is trackable.
3. Switch to the new project; open **Agent Platform** from products/search.
4. Click **Enable APIs** on first access (takes a couple of minutes).
5. Monitor free-credit consumption.

### Step 2: Authenticate (Application Default Credentials)
- In the platform, click **Get API key**. Two options: long-lived credentials (**not recommended**) or **Application Default Credentials / ADC** (**recommended**).
- Run the ADC command shown in the console in the terminal, enter the **project ID**, and authenticate with the right Google account.
- A test request to the Gemini Flash model succeeded, confirming ADC works locally and uses the free credit.

### Step 3: Choose a coding agent
- Installed **Antigravity CLI**; launched with `agy` in the project folder; trusted the folder.
- It connected to the Google account, the Agent Platform, the GCP project and a Gemini Flash model.

### Step 4: Install and configure Agent CLI
- Run the one-line setup command from the video description / Agent CLI page (it was a `uvx ... setup` command.
- It authenticates with the current Google account, installs the CLI, installs **7 skills**, and verifies the setup.

**The 7 skills installed:**
| Skill | Purpose |
|---|---|
| ADK code | Write agent code / build with ADK |
| Deploy | Instructions for deploying the agent (later days) |
| Eval | Agent evaluation (later days) |
| Observability | Monitoring (later days) |
| Publish | Publishing the agent |
| Scaffold | Create initial agent setup and folder structure |
| Workflow | Build with ADK and run locally |

Verify by typing `skills` in the coding agent and confirming all 7 are listed.

## 4. Building the agent

**Prompt used:**
> Build a simple Kubernetes investigation agent in Python that takes logs as input to perform investigation. Post investigation, it should provide a detailed analysis with supporting evidence.

**What happened behind the scenes:**
1. Coding agent invoked **Agent CLI** → created project structure (scaffold).
2. Used the **ADK code** skill instructions → generated `agent.py` and `pyproject.toml`.
3. Ran an `agent-cli install` step → downloaded dependencies.

**Generated artifacts:** agent code, dependency/requirements files, README, tests, optional Docker run support.

**Three ways to run:**
| Method | Command (verify exact names in your generated README) |
|---|---|
| Interactive web UI | `agent-cli playground` |
| CLI run (**recommended; reused later for deploy/observability/governance**) | `agent-cli run <prompt/log file>` |
| Plain Python | `uv run python main.py <logfile>` |

## 5. Test / validation
- Existing cluster had an **nginx pod in a failed state** (`kubectl get pods`).
- Captured `kubectl describe pod <pod-name>` output into `error.txt`.
- Ran: `agent-cli run` with a prompt to investigate `error.txt` and explain in simple words.

**Agent output (v1):**
- Incident type: **container image pull failure**, confidence ~**98%**
- Root cause: image pull failure for the nginx image tag used
- Possible causes: invalid image/repository, missing registry authentication
- Supporting **evidence** cited from the log
- **Impact** and **remediation** steps

> Note: v1 only analyses provided logs; it does **not** connect to the cluster or take action.


## 💡 Key takeaways
1. Agent CLI + coding agent + ADK = agent creation from natural language, no manual code.
2. Skills are what make a coding agent follow ADK best practices.
3. Use a dedicated GCP project for isolation and billing visibility.
4. Prefer ADC over long-lived keys (better security).
5. Agent output includes evidence and confidence, which feeds the **trust** problem solved later via evaluation.
6. Using `agent-cli run` now keeps the workflow consistent for deploy, observe and govern.


