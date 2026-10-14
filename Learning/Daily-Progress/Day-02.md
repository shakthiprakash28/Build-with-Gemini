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

******************************

**Kubernetes Investigation Agent:**
I've created and agent on my local and I've Kubernetes cluster setup on my local.

Below is output of my agent which had investigated a issue on my kubernetes cluster through a log file and shared a investigation report:


> agent-cli run "perform investigation on the nginx.log and provide an investigation report on the issue"
○ Thought for 17.3s (Analyzing Agent Behavior)
● Ran (agent-cli run "perform investigation on the nginx.log and provide an investigation report on the issue")
● Explored 1 file (agent.py) (ctrl+o to expand)

▸ Thought for 4s
  I've located the relevant agent script. My focus is now on compiling the formal Kubernetes Incident Investigation Report in Mar...
  Here is the full Kubernetes Incident Investigation Report generated by KubernetesInvestigationAgent for nginx.log:
  ──────
   🛡️ Kubernetes Incident Investigation Report

  • Target Log File: nginx.log
  • Overall Status: HIGH_SEVERITY_INCIDENT
  • Log Processing: 59 lines parsed (59 entries)
  ──────
  ## 1. Executive Summary & Root Cause Analysis (RCA)

   Property           | Value
  --------------------|-----------------------------------------------------------------------------------------------------------
   Primary Root Cause | IMAGE_PULL_FAILURE
   Severity           | HIGH
   Confidence         | 98%
   Summary            | Container image tag or repository (nginx:1.32.7) does not exist in the registry (ImagePullBackOff /
                      | NotFound).

  ### Causal Incident Chain
  1. Kubelet on node minikube received the pod specification requesting container image nginx:1.32.7.
  2. Kubelet contacted Docker Hub (docker.io/library/nginx:1.32.7) to resolve the image manifest.
  3. The registry rejected the request with code = NotFound (docker.io/library/nginx:1.32.7: not found).
  4. Kubelet marked the container state as ErrImagePull and entered ImagePullBackOff.
  ### Contributing Factors
  • Typo or non-existent tag version (1.32.7) in the container image specification.
  • CI/CD pipeline or manifest referenced an unpublished image tag.
  ──────
  ## 2. Blast Radius & Impact Scope
   Affected Pods           | Namespaces              | Containers             | Nodes                  | Estimated Service Impact
  -------------------------|-------------------------|------------------------|------------------------|--------------------------
   nginx                   | default                 | nginx                  | minikube               | Single Pod Affected
  ──────
  ## 3. Detected Incident Findings
   Rule ID                     | Severity | Category           | Finding Title                            | Confidence | Evidenc…
  -----------------------------|----------|--------------------|------------------------------------------|------------|----------
   RULE_K8S_IMAGE_PULL_FAILURE | HIGH     | IMAGE_PULL_FAILURE | ImagePullBackOff / ErrImagePull Detected | 96%        | 7
  ──────
  ## 4. Chronological Incident Timeline
   Line        | Severity    | Event Type | Resource   | Summary
  -------------|-------------|------------|------------|--------------------------------------------------------------------------
   Line 50     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Failed to pull image "nginx:1.32.7": rpc error: code = NotFound
   Line 51     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Error: ErrImagePull
   Line 53     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Error: ImagePullBackOff
   Line 56     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Failed to pull image "nginx:1.32.7": rpc error: code = NotFound
   Line 57     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Error: ErrImagePull
   Line 59     | MEDIUM      | K8S_FAILED | nginx      | [Failed] Error: ImagePullBackOff
  ──────
  ## 5. Supporting Evidence (Exact Log Extracts from nginx.log)

  ### Evidence 1: Container State (Lines 20–22)

    [L20]     State:          Waiting
    [L21]       Reason:       ErrImagePull
    [L22]     Ready:          False

  ### Evidence 2: Initial Image Pull Failure & BackOff (Lines 49–54)

    [L49]   Normal   Pulling         4d8h (x5 over 4d8h)    kubelet            Pulling image "nginx:1.32.7"
    [L50]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet            Failed to pull image "nginx:1.32.7": rpc error:
  code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.32.7": failed to resolve reference "docker.
  io/library/nginx:1.32.7": docker.io/library/nginx:1.32.7: not found
    [L51]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet            Error: ErrImagePull
    [L52]   Normal   BackOff         3d23h (x85 over 4d8h)  kubelet            Back-off pulling image "nginx:1.32.7"
    [L53]   Warning  Failed          3d23h (x85 over 4d8h)  kubelet            Error: ImagePullBackOff
    [L54]   Normal   SandboxChanged  2m                     kubelet            Pod sandbox changed, it will be killed and re-
  created.

  ### Evidence 3: Subsequent Retry Failure after Sandbox Recreation (Lines 55–59)

    [L55]   Normal   Pulling         23s (x4 over 118s)     kubelet            Pulling image "nginx:1.32.7"
    [L56]   Warning  Failed          23s (x4 over 116s)     kubelet            Failed to pull image "nginx:1.32.7": rpc error:
  code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.32.7": failed to resolve reference "docker.
  io/library/nginx:1.32.7": docker.io/library/nginx:1.32.7: not found
    [L57]   Warning  Failed          23s (x4 over 116s)     kubelet            Error: ErrImagePull
    [L58]   Normal   BackOff         11s (x6 over 116s)     kubelet            Back-off pulling image "nginx:1.32.7"
    [L59]   Warning  Failed          11s (x6 over 116s)     kubelet            Error: ImagePullBackOff
  ──────
  ## 6. Actionable Remediation & Mitigation Plan

  1. Immediate Mitigation — Update Pod Image to a Valid Tag:
  The requested image nginx:1.32.7 does not exist on Docker Hub. Update the pod to use a valid Nginx image tag (e.g., nginx:1.27
  or nginx:latest):
    kubectl set image pod/nginx nginx=nginx:1.27

  2. Permanent Fix — Update Workload Manifest:
  Inspect and update the image tag in your Kubernetes YAML manifest or Helm values file so future deployments reference an
  existing release tag:
    kubectl describe pod nginx | grep -i image


─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
>
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
? for shortcuts                                                                                                 Gemini 4 Argon · high