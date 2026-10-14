# Day 4: Evaluating the Agent (Datasets, Traces, Scoring, Regression Compare)

## 🎯 Objectives
- Understand **why a correct answer on one incident doesn't prove the agent is reliable**.
- Run the full **evaluation workflow** with Agent CLI: synthesize dataset → generate traces → grade → improve → re-grade → compare.
- Use evaluation to find a real gap (missing node information), fix it with a new tool, and show measurable improvement.

## 1. Why evaluate? (the motivating failure)
Day 3's agent solved an `ImagePullBackOff` incident correctly, but one success isn't proof. On a different incident it may **hallucinate** and give a wrong report, which is dangerous in production.

### Live demonstration of a hallucination
| Item | Detail |
|---|---|
| Setup | Local **kind** cluster; "payments" app with a **MySQL** deployment |
| Deliberate fault | Memory limit set to **128 MB**, while MySQL needs about **400 MB** at initialisation |
| Real outcome | Pod runs, then is **OOMKilled** within ~30 seconds (CrashLoopBackOff afterwards) |
| Agent report | "Container startup failure / CrashLoopBackOff", **95% confidence**, listed causes such as missing env vars, signals, filesystem permissions. **No mention of OOM**, not even in remediation |

### Root cause of the miss
- The agent only had 3 tools: `get_pod_logs`, `get_pod_events`, `get_deployment_history`.
- Checked manually: logs show only initialisation output, events only show "Back-off restarting failed container", and deployment history is empty (first deployment).
- **None of the tools exposed the OOMKilled signal** → the LLM filled the gap by guessing.

> **Lesson:** If tools don't return the needed data, the agent will **hallucinate with high confidence**. Confidence scores alone are not proof of correctness.

## 2. Evaluation workflow (5 steps)

| Step | Purpose | Agent CLI command (per video; verify exact syntax in the evaluation guide) |
|---|---|---|
| 1. **Synthesize dataset** | Auto-generate realistic incident test cases, each with an input and an expected root cause/response | `eval dataset synthesize -n <count>` |
| 2. **Generate traces** | Run the agent on every case and record what it did (prompts, tool calls, output) | `eval generate` |
| 3. **Configure & grade** | Choose scoring criteria, then score the traces | `eval` grade/score using the config file |
| 4. **Improve & re-run** | Fix the agent, regenerate traces with the *same* dataset, re-grade | repeat steps 2–3 |
| 5. **Compare (regression)** | Compare latest results to a baseline to see if the change helped or broke things | `eval compare` |

Evaluation checks two things:
1. Did the agent reach the **right root cause**?
2. Did it get there **sensibly**, using the right information with no unnecessary steps?

### Doing it with natural language
The **eval skill** (installed on Day 2) tells the coding agent how to run these commands. You don't type CLI commands; you prompt, and the coding agent builds and runs them.

| Step | Prompt used |
|---|---|
| Synthesize | "Synthesize 10 Kubernetes incident test cases for our evaluation dataset related to OOM kill, CPU throttling, container crash, crash loop back off, node memory pressure, node not ready, readiness probe incorrect, resource request limits, service has no endpoints, service routes to unhealthy pods." |
| Traces | "Execute the agent on this test dataset and generate the traces." |
| Grade | "Grade the recorded traces and show me the test scorecard." |
| Fix | "Add a tool called get_nodes_info to the Kubernetes investigation agent so that it can analyze node-related issues." |
| Compare | "Compare our latest test results against the baseline using eval compare." |

## 3. Step details

### Step 1: Dataset
- The coding agent read the eval skill and the agent codebase, then ran dataset synthesis with `-n 10`.
- It **spawned 4 sub-agents** (2–3 cases each) and **merged** their outputs into one JSON file (named like `synthesized_10_incidents.json`; a clearer name such as `k8s_incidents.json` is better).
- Each case has an **input** (a realistic user scenario, e.g. "my training job pod died unexpectedly in the backend namespace") and an **expected response** (incident type, e.g. pod termination, or CrashLoopBackOff with API endpoint offline as the cause).
- Good practice: cover a **wide range** of failure types so the agent is tested thoroughly.

### Step 2: Traces
- Output goes to the `artifacts/traces` folder as a timestamped JSON file.
- Each trace shows the user scenario, the **system prompt** (a senior Kubernetes SRE/forensic specialist with the tools and an investigation protocol), and the agent's response.
- Reviewing traces exposes poor reasoning. Example: a case about a namespace's pod disappearing/evicted got an unrelated "API server connection refused / DNS" answer.

### Step 3: Scoring
- Config file: **`eval config`** in the `test/eval` folder (YAML). It sets the metric used.
- Default here: a **custom response-quality** metric (a Python file generated with the agent).
- Other metrics: **tool quality**, **general quality**, formatting rules, etc. (see `eval metric list` in the guide). Start with the default, then refine.
- Output: JSON and **HTML report** (the HTML is easier to read).

### Results
| Run | Mean score | Std dev | Notes |
|---|---|---|---|
| **Baseline** (3 tools) | **4.7 / 5** | 0.9487 | Case 1 scored 5/5. **Case 7 (pod scheduling failure) scored 2/5** |
| **After adding `get_nodes_info`** | **5.0 / 5** | 0 | Previously weak cases (7 and 8) now 5/5 |

**Why case 7 failed:** The agent claimed multiple nodes had untolerated taints and insufficient CPU/memory, but the kind cluster has a **single node** (`kubectl get nodes`). No tool could read node data, so it hallucinated. Other low scorers were also node-related.

### Step 4: Fix
- Added `get_nodes_info` via a prompt; the coding agent used the ADK code skill and updated **`agent.py`** (tool list) and **`tools.py`** (implementation).
- Dataset **unchanged**; only traces regenerated and re-graded, so the comparison is fair.

### Step 5: Compare
- Treat the earlier results as the **baseline** and compare with the new results using `eval compare`. Useful for **regression testing** after any future agent change.

## 4. Updated agent (v3)
| Tool | Purpose |
|---|---|
| `get_pod_logs` | Container logs |
| `get_pod_events` | Pod events |
| `get_deployment_history` | Recent version/deployment changes |
| **`get_nodes_info`** (new) | Node count, status, capacity, conditions |

## 5. Notes to add for reviewers (my observations)
- The video's **OOMKilled MySQL scenario** was shown as the failure demo; the 10-case dataset was then used for scoring. The notes don't state that the dataset was re-run specifically on the OOM scenario, so consider adding an OOM case and showing the agent's report before and after. *(Verify yourself; the video doesn't show this.)*
- A synthesized 10-case set scoring 5/5 is encouraging but small. For production confidence, plan more cases, harder cases, and metrics beyond one response-quality score.
- Scores are produced by an automated grader, so spot-check some cases manually.

## 💡 Key takeaways
1. A working demo is not evidence of reliability; **evaluation provides measurable evidence**.
2. **Missing tools cause hallucination.** Evaluation reveals *which* tool or data is missing.
3. The loop is: **dataset → traces → score → fix → re-run → compare**.
4. Keep the **dataset fixed** when comparing agent versions.
5. Traces show *how* the agent reasoned, not just the final answer.
6. The eval skill lets you run the whole workflow from plain-English prompts.
7. Compare against a baseline to catch **regressions** after changes.

## ⏭ Next
**Deploy the agent to production** (Agent Runtime).

