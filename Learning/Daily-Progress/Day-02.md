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

## **Kubernetes Investigation Agent:**

I've created and agent on my local and I've Kubernetes cluster setup on my local.

Below is output of my agent which had investigated a issue on my kubernetes cluster through a log file and shared a investigation report:

## **Scenario 1: Image_Pull_Failure** 

shakt@DESKTOP-RDBL7GP MINGW64 /d/Build-with-Gemini/Projects/K8s-Investigation-Agent (main)
$ agent-cli run "Investigate the pod failure from the attached log file D:\Build-with-Gemini\Projects\K8s-Investigation-Agent\nginx.log"
┌──────────────── 🔍 Kubernetes Incident Investigation Report ────────────────┐
│ Investigation ID: k8s-inv-95cbb4bb                                          │
│ Status: HIGH_SEVERITY_INCIDENT  |  Processed 59 lines (59 entries) in 0.01s │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
┌────────────────── ⚡ Root Cause Analysis (Severity: HIGH) ──────────────────┐
│ Category: IMAGE_PULL_FAILURE                                                │
│ Confidence: 98%                                                             │
│ Summary: Container image tag or repository does not exist in registry       │
│ (ImagePullBackOff / 404 Not Found).                                         │
│                                                                             │
│ Causal Chain:                                                               │
│   1. Kubelet received pod specification requesting container image          │
│   2. Kubelet contacted remote container registry to resolve image manifest  │
│   3. Registry rejected request with 'Not Found' (tag or repository does not │
│ exist)                                                                      │
│   4. Kubelet marked container state as ErrImagePull and backed off with     │
│ ImagePullBackOff                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                        🎯 Blast Radius & Impact Scope
┌───────────────┬────────────┬────────────┬──────────┬────────────────────────┐
│               │            │            │          │ Estimated Service      │
│ Affected Pods │ Namespaces │ Containers │ Nodes    │ Impact                 │
├───────────────┼────────────┼────────────┼──────────┼────────────────────────┤
│ nginx         │ default    │ nginx      │ minikube │ Single Pod Affected    │
└───────────────┴────────────┴────────────┴──────────┴────────────────────────┘

                         📋 Detected Incident Findings
┌──────────────┬────────────────────────┬─────┬──────────────┬────────────────┐
│              │                        │ Fi… │              │                │
│   Severity   │ Category               │ Ti… │   Confidence │ Evidence Count │
├──────────────┼────────────────────────┼─────┼──────────────┼────────────────┤
│   🟠 HIGH    │ IMAGE_PULL_FAILURE     │ Im… │          96% │       7        │
│              │                        │ /   │              │                │
│              │                        │ Er… │              │                │
│              │                        │ De… │              │                │
└──────────────┴────────────────────────┴─────┴──────────────┴────────────────┘

⏱️  Chronological Incident Timeline
├── Line 50 (Line 50) : K8S_FAILED - [Failed] Failed to pull image
│   "nginx:1.32.7": rpc error: code = NotFound desc = failed to
├── Line 51 (Line 51) : K8S_FAILED - [Failed] Error: ErrImagePull
├── Line 53 (Line 53) : K8S_FAILED - [Failed] Error: ImagePullBackOff
├── Line 56 (Line 56) : K8S_FAILED - [Failed] Failed to pull image
│   "nginx:1.32.7": rpc error: code = NotFound desc = failed to
├── Line 57 (Line 57) : K8S_FAILED - [Failed] Error: ErrImagePull
└── Line 59 (Line 59) : K8S_FAILED - [Failed] Error: ImagePullBackOff

🔬 Supporting Evidence (Exact Log Extracts)

┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 20-22 ──────┐
│ [L20]     State:          Waiting                                           │
│ [L21]       Reason:       ErrImagePull                                      │
│ [L22]     Ready:          False                                             │
└───────────────── Reason: Image pull error: 'ErrImagePull' ──────────────────┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 49-51 ──────┐
│ [L49]   Normal   Pulling         4d8h (x5 over 4d8h)    kubelet             │
│ [L50]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet             │
│ [L51]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet             │
└─ Reason: Image pull error: 'Failed to pull image "nginx:1.32.7": rpc error:─┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 50-52 ──────┐
│ [L50]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet             │
│ [L51]   Warning  Failed          4d8h (x5 over 4d8h)    kubelet             │
│ [L52]   Normal   BackOff         3d23h (x85 over 4d8h)  kubelet             │
└───────────────── Reason: Image pull error: 'ErrImagePull' ──────────────────┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 52-54 ──────┐
│ [L52]   Normal   BackOff         3d23h (x85 over 4d8h)  kubelet             │
│ [L53]   Warning  Failed          3d23h (x85 over 4d8h)  kubelet             │
│ [L54]   Normal   SandboxChanged  2m                     kubelet             │
└─────────────── Reason: Image pull error: 'ImagePullBackOff' ────────────────┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 55-57 ──────┐
│ [L55]   Normal   Pulling         23s (x4 over 118s)     kubelet             │
│ [L56]   Warning  Failed          23s (x4 over 116s)     kubelet             │
│ [L57]   Warning  Failed          23s (x4 over 116s)     kubelet             │
└─ Reason: Image pull error: 'Failed to pull image "nginx:1.32.7": rpc error:─┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 56-58 ──────┐
│ [L56]   Warning  Failed          23s (x4 over 116s)     kubelet             │
│ [L57]   Warning  Failed          23s (x4 over 116s)     kubelet             │
│ [L58]   Normal   BackOff         11s (x6 over 116s)     kubelet             │
└───────────────── Reason: Image pull error: 'ErrImagePull' ──────────────────┘
┌────── Finding: ImagePullBackOff / ErrImagePull Detected | Lines 58-59 ──────┐
│ [L58]   Normal   BackOff         11s (x6 over 116s)     kubelet             │
│ [L59]   Warning  Failed          11s (x6 over 116s)     kubelet             │
└─────────────── Reason: Image pull error: 'ImagePullBackOff' ────────────────┘
🛠️  Actionable Remediation & Mitigation Plan

[IMMEDIATE MITIGATION] Verify image name/tag on registry and update pod image.
Explanation: The requested image 'nginx:1.32.7' was not found on the registry.
Confirm the correct tag on Docker Hub/registry and update the pod or
deployment.

kubectl set image pod/nginx nginx=<valid-image>:<tag>

[PERMANENT FIX] Correct image tag in workload YAML manifest and re-apply.
Explanation: Verify the image name in git manifests / Helm values matches your
release artifacts.

kubectl describe pod nginx | grep -i image

**Actual Output of the Pod Log:**

shakt@DESKTOP-RDBL7GP MINGW64 /d/Build-with-Gemini/Projects/K8s-Investigation-Agent (main)
$ kubectl describe pod nginx | grep -i image
    Image:          nginx:1.32.7
    Image ID:
      Reason:       ImagePullBackOff
  Normal   BackOff  3m21s (x262 over 103m)  kubelet  Back-off pulling image "nginx:1.32.7"
  Warning  Failed   3m21s (x262 over 103m)  kubelet  Error: ImagePullBackOff

## **Scenario 2: OUt of Memory - OOM** 

PS D:\Build-with-Gemini\Projects\K8s-Investigation-Agent> agent-cli run "Investigate the failure from oom-test.log"
╭─────────────────────────────────────────── 🔍 Kubernetes Incident Investigation Report ───────────────────────────────────────────╮
│ Investigation ID: k8s-inv-f52bb5c3                                                                                                │
│ Status: CRITICAL_FAILURE  |  Processed 77 lines (77 entries) in 0.0175s                                                           │
│                                                                                                                                   │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────────────── ⚡ Root Cause Analysis (Severity: CRITICAL) ───────────────────────────────────────────╮
│ Category: OOM_KILL                                                                                                                │
│ Confidence: 98%                                                                                                                   │
│ Summary: Container Out-Of-Memory (OOMKilled) triggered CrashLoopBackOff restart cycles.                                           │
│                                                                                                                                   │
│ Causal Chain:                                                                                                                     │
│   1. Container memory usage exceeded cgroup limit                                                                                 │
│   2. Linux kernel / kubelet invoked OOM Killer and dispatched SIGKILL (exit code 137)                                             │
│   3. Container exited abruptly                                                                                                    │
│   4. Kubelet repeatedly restarted container, entering CrashLoopBackOff                                                            │
│                                                                                                                                   │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                                   🎯 Blast Radius & Impact Scope
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Affected Pods              ┃ Namespaces ┃ Containers ┃ Nodes    ┃ Estimated Service Impact        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ oom-test, oom-test_default │ default    │ stress     │ minikube │ Multiple Pods Affected (2 pods) │
└────────────────────────────┴────────────┴────────────┴──────────┴─────────────────────────────────┘

                                                    📋 Detected Incident Findings
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃   Severity   ┃ Category               ┃ Finding Title                                             ┃   Confidence ┃ Evidence Count ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ 🔴 CRITICAL  │ OOM_KILL               │ Container Terminated Due To Out-Of-Memory (OOMKilled /    │          98% │       2        │
│              │                        │ Exit 137)                                                 │              │                │
│ 🔴 CRITICAL  │ CRASH_LOOP             │ Pod In CrashLoopBackOff / Repeated Process Failure        │          95% │       3        │
└──────────────┴────────────────────────┴───────────────────────────────────────────────────────────┴──────────────┴────────────────┘

⏱️  Chronological Incident Timeline
├── Line 29 (Line 29) : ERROR - Reason:       OOMKilled
└── Line 76 (Line 76) : K8S_BACKOFF - [BackOff] Back-off restarting failed container stress in pod oom-test_default(3a1d2db3-cac

🔬 Supporting Evidence (Exact Log Extracts)

╭───────────────────── Finding: Container Terminated Due To Out-Of-Memory (OOMKilled / Exit 137) | Lines 28-30 ─────────────────────╮
│ [L28]     State:          Terminated                                                                                              │
│ [L29]       Reason:       OOMKilled                                                                                               │
│ [L30]       Exit Code:    1                                                                                                       │
╰─────────────────────────────────────── Reason: Detected OOM memory exhaustion: 'OOMKilled' ───────────────────────────────────────╯
╭───────────────────── Finding: Container Terminated Due To Out-Of-Memory (OOMKilled / Exit 137) | Lines 33-35 ─────────────────────╮
│ [L33]     Last State:     Terminated                                                                                              │
│ [L34]       Reason:       OOMKilled                                                                                               │
│ [L35]       Exit Code:    1                                                                                                       │
╰─────────────────────────────────────── Reason: Detected OOM memory exhaustion: 'OOMKilled' ───────────────────────────────────────╯
╭──────────────────────────── Finding: Pod In CrashLoopBackOff / Repeated Process Failure | Lines 29-31 ────────────────────────────╮
│ [L29]       Reason:       OOMKilled                                                                                               │
│ [L30]       Exit Code:    1                                                                                                       │
│ [L31]       Started:      Wed, 14 Oct 2026 12:51:07 +0100                                                                         │
╰─────────────────────────────── Reason: Container failure / CrashLoop indicator: 'Exit Code:    1' ────────────────────────────────╯
╭──────────────────────────── Finding: Pod In CrashLoopBackOff / Repeated Process Failure | Lines 34-36 ────────────────────────────╮
│ [L34]       Reason:       OOMKilled                                                                                               │
│ [L35]       Exit Code:    1                                                                                                       │
│ [L36]       Started:      Wed, 14 Oct 2026 12:50:24 +0100                                                                         │
╰─────────────────────────────── Reason: Container failure / CrashLoop indicator: 'Exit Code:    1' ────────────────────────────────╯
╭──────────────────────────── Finding: Pod In CrashLoopBackOff / Repeated Process Failure | Lines 75-77 ────────────────────────────╮
│ [L75]   Normal   Started    12s (x5 over 94s)  kubelet            Container started                                               │
│ [L76]   Warning  BackOff    12s (x5 over 91s)  kubelet            Back-off restarting failed container stress in pod oom-test_def │
│ [L77]   Normal   Pulled     12s                kubelet            Successfully pulled image "polinux/stress" in 1.187s (1.187s in │
╰───────────────── Reason: Container failure / CrashLoop indicator: 'Back-off restarting failed container stress' ──────────────────╯
🛠️  Actionable Remediation & Mitigation Plan

[IMMEDIATE MITIGATION] Increase container memory limits to restore service stability.
Explanation: Prevents the Linux cgroup OOM killer from killing the process immediately upon memory spikes.

kubectl set resources deployment/<deployment-name> --limits=memory=1Gi --requests=memory=512Mi
spec:
  template:
    spec:
      containers:
      - name: app
        resources:
          requests:
            memory: "512Mi"
          limits:
            memory: "1Gi"

[PERMANENT FIX] Capture heap dumps or profile application memory usage.
Explanation: Identifies memory leaks, unclosed database connection pools, or runaway caching algorithms.

kubectl logs oom-test --previous | grep -i -E 'oom|memory|heap'

PS D:\Build-with-Gemini\Projects\K8s-Investigation-Agent> kubectl get pod
NAME       READY   STATUS             RESTARTS       AGE
nginx      0/1     ImagePullBackOff   0              4d11h
oom-test   0/1     OOMKilled          5 (2m1s ago)   3m24s
PS D:\Build-with-Gemini\Projects\K8s-Investigation-Agent>