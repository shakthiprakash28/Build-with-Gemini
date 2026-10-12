# 🔍 Kubernetes Log Investigation Agent

An autonomous Kubernetes log investigation and incident analysis agent in Python. It ingests raw logs (pod streams, node events, kubelet logs, CRI containerd/Docker streams, and multi-line application stack traces), performs automated root cause analysis (RCA), extracts exact log evidence citations, computes the blast radius, and generates actionable remediation commands and YAML patches.

---

## 🚀 Key Features

- **Multi-Format Ingestion**: Seamlessly parses Container Runtime Interface (CRI) logs, kubelet system logs, `kubectl describe` / `kubectl get events` tables, structured JSON logs, and multi-line exception stack traces (Java, Python, Go, Node.js).
- **Offline & Autonomous Deterministic Diagnosis**: Ships with 9 built-in diagnostic rule engines covering the most prevalent Kubernetes production failure modes. Operates 100% offline without requiring external API keys.
- **Causal Correlation Engine**: Disentangles cascades of failure symptoms to isolate the true root cause (e.g., distinguishing an underlying CoreDNS resolution timeout from a cascading probe failure and CrashLoopBackOff).
- **Evidence-Backed Analysis**: Cites exact log extracts with line numbers, timestamps, and matched regex patterns to provide irrefutable post-mortem evidence.
- **Blast Radius & Impact Scope**: Identifies affected pods, containers, namespaces, and nodes to classify service impact.
- **Actionable Remediation**: Delivers copy-pasteable `kubectl` commands and declarative Kubernetes YAML patches for immediate mitigation and permanent fixes.
- **Multi-Format Reporting**: Outputs rich terminal interactive dashboards, GitHub-flavored Markdown post-mortem reports, and structured JSON for CI/CD or ticketing integrations.
- **Optional AI Synthesis**: Optional Google Gemini LLM integration (`--llm`) for executive summary enrichment and advisory commentary.

---

## 📦 Supported Failure Modes & Diagnostic Rules

| Rule ID | Failure Category | Detection Signatures |
| :--- | :--- | :--- |
| `RULE_K8S_OOM_KILL` | **OOM_KILL** | `OOMKilled`, Linux cgroup exit code 137, JVM `OutOfMemoryError`, Go runtime memory limit, Node.js heap exhaustion |
| `RULE_K8S_CRASHLOOP_BACKOFF` | **CRASH_LOOP** | `CrashLoopBackOff`, container exit codes `1`, `2`, `134`, `139`, `143`, kubelet restart backoff |
| `RULE_K8S_PROBE_FAILURE` | **PROBE_FAILURE** | Liveness, readiness, and startup probe failures, HTTP 5xx probe errors, probe timeout events |
| `RULE_K8S_NETWORK_DNS` | **NETWORK_DNS_FAILURE** | CoreDNS `i/o timeout` (port 53), `no such host` (NXDOMAIN), TCP connection refused/reset, TLS handshake errors |
| `RULE_K8S_IMAGE_PULL` | **IMAGE_PULL_FAILURE** | `ImagePullBackOff`, `ErrImagePull`, registry 401/403 unauthorized, image pull rate limits |
| `RULE_K8S_RBAC_AUTH` | **RBAC_AUTH_FAILURE** | HTTP 403 Forbidden, `secrets is forbidden: User ... cannot list resource`, missing Role/RoleBinding |
| `RULE_K8S_STORAGE_PVC` | **STORAGE_PVC_FAILURE** | `Multi-Attach error for volume`, `FailedMount`, `VolumeBindingFailed`, volume already attached to another node |
| `RULE_K8S_SCHEDULING` | **SCHEDULING_NODE_FAILURE** | `FailedScheduling`, `0/N nodes available: Insufficient memory/cpu`, untolerated node taints |
| `RULE_K8S_APP_PANIC` | **APPLICATION_PANIC** | Unhandled Go runtime panics, Python Tracebacks, Java unhandled exceptions, Node.js uncaught exceptions |

---

## 🛠️ Installation

### 1. Standard Installation
```bash
git clone https://github.com/example/k8s-investigation-agent.git
cd k8s-investigation-agent
pip install -e .
```

### 2. Using Requirements
```bash
pip install -r requirements.txt
```

### 3. Optional Gemini AI Advisor
```bash
pip install ".[ai]"
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 💻 CLI Usage Guide

The agent provides the `k8s-investigate` command-line tool.

### 1. Investigate a Single Log File
```bash
k8s-investigate sample_logs/oom_killed_crashloop.log
```

### 2. Investigate an Entire Directory of Pod Logs
```bash
k8s-investigate -d /var/log/pods/ -n production
```

### 3. Stream Directly from `kubectl` via STDIN
```bash
kubectl logs deployment/payment-service --previous | k8s-investigate
# or
kubectl get events -n prod --sort-by='.metadata.creationTimestamp' | k8s-investigate
```

### 4. Export Post-Mortem Report to Markdown or JSON
```bash
# Generate Markdown post-mortem report
k8s-investigate sample_logs/rbac_forbidden_error.log --format markdown -o postmortem.md

# Generate structured JSON for automation or SIEM
k8s-investigate sample_logs/coredns_timeout_probe_failure.log --format json -o incident.json
```

### 5. CLI Options Reference
```
Usage: k8s-investigate [OPTIONS] [LOG_FILE]

Options:
  -f, --file PATH         Path to a log file or event dump.
  -d, --dir PATH          Directory of log files to analyze.
  -n, --namespace TEXT    Default Kubernetes namespace filter.
  -o, --output PATH       Write report to output file instead of stdout.
  --format [terminal|markdown|json]
                          Output report format. [default: terminal]
  --llm                   Enrich diagnosis with Google Gemini AI synthesis.
  --quiet                 Suppress non-essential console output.
  --help                  Show this message and exit.
```

---

## 🐍 Python API Usage

You can embed the investigation engine into your own Python automation scripts, incident bots, or operators:

```python
from k8s_investigate import KubernetesInvestigationAgent

# Initialize agent
agent = KubernetesInvestigationAgent()

# Investigate a log file
report = agent.investigate_file("sample_logs/oom_killed_crashloop.log")

# Access structured findings and RCA
print(f"Primary Root Cause: {report.root_cause.category.value}")
print(f"Confidence: {report.root_cause.confidence * 100}%")
print(f"Summary: {report.root_cause.summary}")

# Iterate through supporting evidence snippets
for finding in report.findings:
    print(f"\nFinding: {finding.title}")
    for snippet in finding.evidence:
        print(f"  Lines {snippet.start_line}-{snippet.end_line}: {snippet.highlighted_reason}")

# Access copy-pasteable remediation commands
for action in report.remediations:
    print(f"\nRemediation ({action.action_type}): {action.description}")
    if action.kubectl_command:
        print(f"  Command: {action.kubectl_command}")

# Export to Markdown or JSON
markdown_report = agent.to_markdown(report)
json_data = agent.to_json(report)
```

---

## 🔬 Sample Investigation Output

When investigating an Out-Of-Memory incident (`sample_logs/oom_killed_crashloop.log`), the agent produces:

```
┌──────────────── 🔍 Kubernetes Incident Investigation Report ────────────────┐
│ Investigation ID: k8s-inv-7f394464                                          │
│ Status: CRITICAL_FAILURE  |  Processed 14 lines (14 entries) in 0.007s      │
└─────────────────────────────────────────────────────────────────────────────┘
┌──────────────── ⚡ Root Cause Analysis (Severity: CRITICAL) ─────────────────┐
│ Category: OOM_KILL                                                          │
│ Confidence: 98%                                                             │
│ Summary: Container was killed by Linux OOM killer or Kubernetes kubelet     │
│ (exit code 137).                                                            │
│                                                                             │
│ Causal Chain:                                                               │
│   1. Application memory consumption exceeded cgroup resource limit (512Mi)  │
│   2. Linux kernel invoked oom-killer or JVM threw OutOfMemoryError          │
│   3. Container exited abruptly with exit code 137                           │
│   4. Kubelet repeatedly restarted container, entering CrashLoopBackOff      │
└─────────────────────────────────────────────────────────────────────────────┘
                        🎯 Blast Radius & Impact Scope                         
┌──────────────────────────────────────┬────────────┬─────────────┬───────────┐
│ Affected Pods                        │ Namespaces │ Containers  │ Impact    │
├──────────────────────────────────────┼────────────┼─────────────┼───────────┤
│ payment-service-7d84bf9bc-5k9lm_prod │ prod       │ payment-app │ 1 Pod     │
└──────────────────────────────────────┴────────────┴─────────────┴───────────┘

                         📋 Detected Incident Findings                         
┌──────────────┬────────────┬──────────────────────────────────┬────────┬─────┐
│ Severity     │ Category   │ Finding Title                    │ Conf.  │ Ev. │
├──────────────┼────────────┼──────────────────────────────────┼────────┼─────┤
│ 🔴 CRITICAL  │ OOM_KILL   │ Container Terminated (OOMKilled) │ 98%    │ 3   │
│ 🔴 CRITICAL  │ CRASH_LOOP │ Pod In CrashLoopBackOff          │ 95%    │ 4   │
└──────────────┴────────────┴──────────────────────────────────┴────────┴─────┘

🔬 Supporting Evidence (Exact Log Extracts)
┌─ Finding: Container Terminated Due To Out-Of-Memory (OOMKilled / Exit 137) ─┐
│ [L5] [WARN] [payment-service] Memory consumption climbing: heap used 480MB  │
│ [L6] java.lang.OutOfMemoryError: Java heap space                            │
│ [L7]  at java.base/java.util.Arrays.copyOf(Arrays.java:3516)                │
└─ Reason: Detected OOM memory exhaustion: 'java.lang.OutOfMemoryError' ──────┘

🛠️  Actionable Remediation & Mitigation Plan
[IMMEDIATE MITIGATION] Increase container memory limits:
  kubectl set resources deployment/<deployment-name> --limits=memory=1Gi --requests=memory=512Mi

[PERMANENT FIX] Profile application memory and capture heap dumps:
  kubectl logs payment-service-7d84bf9bc-5k9lm_prod --previous | grep -i -E 'oom|memory|heap'
```

---

## 🧪 Running Tests

The test suite covers log parsing across all formats, individual diagnostic rule accuracy, engine causal resolution, and CLI operations:

```bash
python -m pytest -v
```

```
tests/test_agent.py::test_agent_investigate_string PASSED                [  4%]
tests/test_agent.py::test_agent_investigate_sample_file PASSED           [  9%]
tests/test_agent.py::test_agent_markdown_and_json_serialization PASSED   [ 13%]
tests/test_cli.py::test_cli_help PASSED                                  [ 18%]
tests/test_cli.py::test_cli_file_run PASSED                              [ 22%]
tests/test_cli.py::test_cli_export_json PASSED                           [ 27%]
tests/test_cli.py::test_cli_export_markdown PASSED                       [ 31%]
tests/test_engine.py::test_causal_resolution_oom_over_crashloop PASSED   [ 36%]
tests/test_engine.py::test_causal_resolution_dns_over_probe PASSED       [ 40%]
tests/test_engine.py::test_timeline_ordering PASSED                      [ 45%]
tests/test_parser.py::test_parse_cri_format PASSED                       [ 50%]
tests/test_parser.py::test_parse_json_format PASSED                      [ 54%]
tests/test_parser.py::test_parse_k8s_event_table PASSED                  [ 59%]
tests/test_parser.py::test_parse_multiline_stack_trace PASSED            [ 63%]
tests/test_rules.py::test_oom_rule_detection PASSED                      [ 68%]
tests/test_rules.py::test_crashloop_rule_detection PASSED                [ 72%]
tests/test_rules.py::test_probe_rule_detection PASSED                    [ 77%]
tests/test_rules.py::test_network_dns_rule_detection PASSED              [ 81%]
tests/test_rules.py::test_image_pull_rule_detection PASSED               [ 86%]
tests/test_rules.py::test_rbac_rule_detection PASSED                     [ 90%]
tests/test_rules.py::test_storage_rule_detection PASSED                  [ 95%]
tests/test_rules.py::test_scheduling_rule_detection PASSED               [100%]

============================= 22 passed in 0.60s ==============================
```

---

## 📄 License
Apache License 2.0.
