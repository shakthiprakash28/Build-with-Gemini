# 🔍 Kubernetes Investigation Agent — Evaluation Dataset Execution Traces

## 1. Executive Benchmark Summary

- **Dataset**: `K8s-Investigation-Agent Incident Evaluation Benchmark` (`v1.0.0`)
- **Total Test Cases Executed**: `10`
- **Passed Cases**: `10 / 10` (**100.0%** accuracy)
- **Total Agent Trace Steps Recorded**: `90` (`9` steps per case)
- **Total Cluster Tool Invocations**: `30` (`get_pod_logs`, `get_pod_events`, `get_deployment_history` per case)
- **Total Diagnostic Rule Evaluations**: `90` (`9` rules × `10` cases)
- **Total Suite Execution Time**: `134.72 ms` (avg `9.27 ms` / case)

## 2. Summary of Executed Test Cases & Traces

| ID | Incident Scenario | Target Pod (`Namespace`) | Tools Invoked | Matched Rules | Root Cause (`Subtype`) | Severity | Confidence | Latency | Verdict | Trace File |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | OOM Kill (Container Memory Limit Exceeded) | `recommendation-engine-6b8f9c4d2-x7v2p` (`ml-serving`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_OOM_KILL, RULE_K8S_CRASHLOOP_BACKOFF` | `OOM_KILL` | `CRITICAL` | `98%` | `16.37 ms` | **PASS (100%)** | `tc01_oom_kill_trace.json` |
| **TC-02** | CPU Throttling (CFS Quota Exhaustion) | `pricing-calculator-7c9d4b5f8-m2k9l` (`commerce`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_SCHEDULING_FAILURE` | `SCHEDULING_NODE_FAILURE` (`CPU_THROTTLING`) | `HIGH` | `94%` | `8.36 ms` | **PASS (100%)** | `tc02_cpu_throttling_trace.json` |
| **TC-03** | Container Crash (Unhandled Runtime Panic / SIGSEGV) | `invoice-generator-5f7b8d9c1-q4n8w` (`billing`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_CRASHLOOP_BACKOFF, RULE_APPLICATION_PANIC_EXCEPTION` | `APPLICATION_PANIC` | `HIGH` | `90%` | `10.46 ms` | **PASS (100%)** | `tc03_container_crash_trace.json` |
| **TC-04** | CrashLoopBackOff (Missing Secret / Startup Configuration Failure) | `auth-token-service-84d9b6c7f-z9p3x` (`identity`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_CRASHLOOP_BACKOFF` | `CRASH_LOOP` | `CRITICAL` | `95%` | `13.02 ms` | **PASS (100%)** | `tc04_crash_loop_backoff_trace.json` |
| **TC-05** | Node Memory Pressure & Kubelet Pod Eviction | `analytics-aggregator-59b7c4d8e-v6r2t` (`data-pipeline`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_SCHEDULING_FAILURE` | `SCHEDULING_NODE_FAILURE` (`NODE_MEMORY_PRESSURE`) | `CRITICAL` | `96%` | `7.99 ms` | **PASS (100%)** | `tc05_node_memory_pressure_trace.json` |
| **TC-06** | Node Not Ready (PLEG Unhealthy & Container Runtime Hang) | `order-processor-6d4f8b9a2-h5j8k` (`orders`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_SCHEDULING_FAILURE` | `SCHEDULING_NODE_FAILURE` (`NODE_NOT_READY`) | `CRITICAL` | `97%` | `7.02 ms` | **PASS (100%)** | `tc06_node_not_ready_trace.json` |
| **TC-07** | Readiness Probe Misconfigured (Wrong HTTP Path / Port) | `catalog-search-7f8e9d6c4-b3n5m` (`storefront`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_PROBE_FAILURE` | `PROBE_FAILURE` | `HIGH` | `95%` | `7.72 ms` | **PASS (100%)** | `tc07_readiness_probe_incorrect_trace.json` |
| **TC-08** | Resource Request Limits (Unschedulable Pod / Insufficient CPU & Memory) | `fraud-detection-model-9a8b7c6d5-p4l2k` (`risk-engine`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_SCHEDULING_FAILURE` | `SCHEDULING_NODE_FAILURE` (`INSUFFICIENT_CPU`) | `HIGH` | `96%` | `7.21 ms` | **PASS (100%)** | `tc08_resource_request_limits_trace.json` |
| **TC-09** | Service Has No Endpoints (Label Selector Mismatch) | `inventory-service-5c6d7e8f9-t2w4y` (`fulfillment`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_NETWORK_DNS_FAILURE` | `NETWORK_DNS_FAILURE` (`SERVICE_NO_ENDPOINTS`) | `HIGH` | `96%` | `7.09 ms` | **PASS (100%)** | `tc09_service_no_endpoints_trace.json` |
| **TC-10** | Service Routes Traffic to Unhealthy Pods (publishNotReadyAddresses Enabled) | `checkout-gateway-4e5f6a7b8-r9m1c` (`payments`) | `get_pod_logs, get_pod_events, get_deployment_history` | `RULE_K8S_NETWORK_DNS_FAILURE` | `NETWORK_DNS_FAILURE` (`SERVICE_ROUTES_UNHEALTHY_PODS`) | `HIGH` | `95%` | `7.46 ms` | **PASS (100%)** | `tc10_service_routes_unhealthy_pods_trace.json` |

---

## 3. Detailed Step-by-Step Execution Traces

### TC-01: OOM Kill (Container Memory Limit Exceeded) (`trace-tc-01-oom_kill`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod recommendation-engine-6b8f9c4d2-x7v2p in namespace ml-serving"`
- **Source Log File**: `logs/tc01_oom_kill.log` (`9` lines -> `9` parsed entries)
- **Investigation ID**: `k8s-inv-d817852a`
- **Execution Latency**: `16.37 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `3.562` | Extracted pod=`recommendation-engine-6b8f9c4d2-x7v2p`, namespace=`ml-serving` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.006` | Fetched `9` lines (`2425` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.003` | Fetched `4` lines (`1055` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`308` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `3.745` | Parsed `9` entries; levels=`{'INFO': 2, 'WARN': 4, 'ERROR': 3}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `10.510` | Evaluated `9` rules -> matched `2`: `['RULE_K8S_OOM_KILL', 'RULE_K8S_CRASHLOOP_BACKOFF']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.038` | Primary RCA: `OOM_KILL` (`CRITICAL`, conf=`0.98`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.037` | Pods=`['recommendation-engine-6b8f9c4d2-x7v2p']`, NS=`['ml-serving']`, Containers=`['recommendation-worker']`, Nodes=`['node-gpu-pool-02']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.022` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Container Out-Of-Memory (OOMKilled) triggered CrashLoopBackOff restart cycles.
- **Causal Chain**:
  1. Container memory usage exceeded cgroup limit
  1. Linux kernel / kubelet invoked OOM Killer and dispatched SIGKILL (exit code 137)
  1. Container exited abruptly
  1. Kubelet repeatedly restarted container, entering CrashLoopBackOff

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Increase container memory limits to restore service stability.: `kubectl set resources deployment/<deployment-name> --limits=memory=1Gi --requests=memory=512Mi`
- **[PERMANENT_FIX]** Capture heap dumps or profile application memory usage.: `kubectl logs recommendation-engine-6b8f9c4d2-x7v2p --previous | grep -i -E 'oom|memory|heap'`

#### Ground-Truth Evaluation Checks
- **Category Match**: `OOM_KILL` == `OOM_KILL` (`True`)
- **Subtype Match**: `None` == `None` (`True`)
- **Severity Match**: `CRITICAL` == `CRITICAL` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['OOMKilled', 'Memory cgroup out of memory: Killed process', 'exit code 137', 'CrashLoopBackOff']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-02: CPU Throttling (CFS Quota Exhaustion) (`trace-tc-02-cpu_throttling`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod pricing-calculator-7c9d4b5f8-m2k9l in namespace commerce"`
- **Source Log File**: `logs/tc02_cpu_throttling.log` (`6` lines -> `6` parsed entries)
- **Investigation ID**: `k8s-inv-6b2cf1f8`
- **Execution Latency**: `8.36 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.095` | Extracted pod=`pricing-calculator-7c9d4b5f8-m2k9l`, namespace=`commerce` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.007` | Fetched `6` lines (`1425` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.003` | Fetched `1` lines (`259` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.004` | Fetched `8` lines (`286` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.760` | Parsed `6` entries; levels=`{'INFO': 2, 'WARN': 3, 'ERROR': 1}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `6.110` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_SCHEDULING_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.033` | Primary RCA: `SCHEDULING_NODE_FAILURE` / `CPU_THROTTLING` (`HIGH`, conf=`0.94`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.027` | Pods=`['pricing-calculator-7c9d4b5f8-m2k9l']`, NS=`['commerce']`, Containers=`['pricing-api']`, Nodes=`['node-general-04']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.025` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Container CFS CPU Quota Throttling Detected
- **Causal Chain**:
  1. Container CPU usage exceeded configured CFS quota within enforcement period (cpu.cfs_period_us)
  1. Linux kernel CFS bandwidth controller throttled runnable container threads (nr_throttled / throttled_time spike)
  1. Application request processing latency spiked and worker threads stalled

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Increase or remove restrictive CPU CFS limit on the throttled container.: `kubectl set resources deployment/<deployment-name> --limits=cpu=2000m --requests=cpu=500m`
- **[PERMANENT_FIX]** Monitor container CPU usage and tune runtime thread pool concurrency (GOMAXPROCS / UV_THREADPOOL_SIZE).: `kubectl top pod pricing-calculator-7c9d4b5f8-m2k9l --containers`

#### Ground-Truth Evaluation Checks
- **Category Match**: `SCHEDULING_NODE_FAILURE` == `SCHEDULING_NODE_FAILURE` (`True`)
- **Subtype Match**: `CPU_THROTTLING` == `CPU_THROTTLING` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['CPU throttling detected', 'nr_throttled=412', 'throttled_time=', 'CFS quota exceeded']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-03: Container Crash (Unhandled Runtime Panic / SIGSEGV) (`trace-tc-03-container_crash`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod invoice-generator-5f7b8d9c1-q4n8w in namespace billing"`
- **Source Log File**: `logs/tc03_container_crash.log` (`8` lines -> `8` parsed entries)
- **Investigation ID**: `k8s-inv-a3c3fb97`
- **Execution Latency**: `10.46 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.052` | Extracted pod=`invoice-generator-5f7b8d9c1-q4n8w`, namespace=`billing` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `8` lines (`1655` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `1` lines (`210` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`287` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.979` | Parsed `8` entries; levels=`{'INFO': 2, 'WARN': 1, 'FATAL': 1, 'ERROR': 4}`; components=`['running']` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `8.017` | Evaluated `9` rules -> matched `2`: `['RULE_K8S_CRASHLOOP_BACKOFF', 'RULE_APPLICATION_PANIC_EXCEPTION']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.035` | Primary RCA: `APPLICATION_PANIC` (`HIGH`, conf=`0.9`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.024` | Pods=`['invoice-generator-5f7b8d9c1-q4n8w']`, NS=`['billing']`, Containers=`['invoice-worker']`, Nodes=`['node-general-01']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.017` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Application Crash: Go Runtime Panic
- **Causal Chain**:
  1. The application process raised an unhandled exception or panic [Go Runtime Panic]. The error caused the main process thread to crash, terminating the container.

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Inspect the crash stack trace from the terminated container logs.: `kubectl logs invoice-generator-5f7b8d9c1-q4n8w --previous`
- **[PERMANENT_FIX]** Inspect pod termination state, exit code, and environment configuration.: `kubectl describe pod invoice-generator-5f7b8d9c1-q4n8w`

#### Ground-Truth Evaluation Checks
- **Category Match**: `APPLICATION_PANIC` == `APPLICATION_PANIC` (`True`)
- **Subtype Match**: `None` == `None` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['panic: runtime error: invalid memory address or nil pointer dereference', 'SIGSEGV', 'goroutine', 'exit code 2']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-04: CrashLoopBackOff (Missing Secret / Startup Configuration Failure) (`trace-tc-04-crash_loop_backoff`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod auth-token-service-84d9b6c7f-z9p3x in namespace identity"`
- **Source Log File**: `logs/tc04_crash_loop_backoff.log` (`9` lines -> `9` parsed entries)
- **Investigation ID**: `k8s-inv-62927b0f`
- **Execution Latency**: `13.02 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.054` | Extracted pod=`auth-token-service-84d9b6c7f-z9p3x`, namespace=`identity` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `9` lines (`2062` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `3` lines (`723` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`285` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `2.364` | Parsed `9` entries; levels=`{'INFO': 1, 'ERROR': 5, 'WARN': 3}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `10.172` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_CRASHLOOP_BACKOFF']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.027` | Primary RCA: `CRASH_LOOP` (`CRITICAL`, conf=`0.95`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.029` | Pods=`['auth-token-service-84d9b6c7f-z9p3x']`, NS=`['identity']`, Containers=`['auth-server']`, Nodes=`['node-general-03']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.018` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Pod In CrashLoopBackOff / Repeated Process Failure
- **Causal Chain**:
  1. The container is repeatedly failing and entering CrashLoopBackOff (Identified exit codes: 1). Container(s): auth-server, auth-token-service-84d9b6c7f-z9p3x_identity. Kubernetes applies an exponential back-off delay (10s, 20s, 40s ... up to 5m) before attempting to restart the container.

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Inspect the logs of the previous terminated container instance.: `kubectl logs auth-token-service-84d9b6c7f-z9p3x --previous`
- **[PERMANENT_FIX]** Debug container interactively with an ephemeral container.: `kubectl debug -it auth-token-service-84d9b6c7f-z9p3x --image=busybox --target=app`

#### Ground-Truth Evaluation Checks
- **Category Match**: `CRASH_LOOP` == `CRASH_LOOP` (`True`)
- **Subtype Match**: `None` == `None` (`True`)
- **Severity Match**: `CRITICAL` == `CRITICAL` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['CrashLoopBackOff', 'Back-off restarting failed container', 'exit code 1', '/etc/secrets/jwt/private.pem']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-05: Node Memory Pressure & Kubelet Pod Eviction (`trace-tc-05-node_memory_pressure`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod analytics-aggregator-59b7c4d8e-v6r2t in namespace data-pipeline"`
- **Source Log File**: `logs/tc05_node_memory_pressure.log` (`6` lines -> `6` parsed entries)
- **Investigation ID**: `k8s-inv-0b46dc53`
- **Execution Latency**: `7.99 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.056` | Extracted pod=`analytics-aggregator-59b7c4d8e-v6r2t`, namespace=`data-pipeline` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `6` lines (`1577` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `3` lines (`867` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`302` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.576` | Parsed `6` entries; levels=`{'INFO': 1, 'WARN': 3, 'ERROR': 2}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `6.017` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_SCHEDULING_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.023` | Primary RCA: `SCHEDULING_NODE_FAILURE` / `NODE_MEMORY_PRESSURE` (`CRITICAL`, conf=`0.96`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.022` | Pods=`['analytics-aggregator-59b7c4d8e-v6r2t']`, NS=`['data-pipeline']`, Containers=`['spark-executor']`, Nodes=`['node-worker-07']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.022` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Node MemoryPressure & Kubelet Pod Eviction Detected
- **Causal Chain**:
  1. Available memory on worker node dropped below kubelet eviction threshold (memory.available<100Mi)
  1. Kubelet transitioned node condition MemoryPressure to True
  1. Kubelet eviction manager ranked pods by QoS class and evicted workload pods (Reason: Evicted)

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Inspect node MemoryPressure condition, allocatable memory, and evicted pods.: `kubectl describe node node-worker-07 | grep -A 15 -E 'Conditions:|Allocated resources:'`
- **[PERMANENT_FIX]** Clean up evicted pods and set accurate memory requests/limits across workloads.: `kubectl get pods -A --field-selector=status.phase=Failed -o wide`

#### Ground-Truth Evaluation Checks
- **Category Match**: `SCHEDULING_NODE_FAILURE` == `SCHEDULING_NODE_FAILURE` (`True`)
- **Subtype Match**: `NODE_MEMORY_PRESSURE` == `NODE_MEMORY_PRESSURE` (`True`)
- **Severity Match**: `CRITICAL` == `CRITICAL` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['MemoryPressure', 'The node was low on resource: memory', 'Evicted', 'NodeHasInsufficientMemory']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-06: Node Not Ready (PLEG Unhealthy & Container Runtime Hang) (`trace-tc-06-node_not_ready`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod order-processor-6d4f8b9a2-h5j8k in namespace orders"`
- **Source Log File**: `logs/tc06_node_not_ready.log` (`6` lines -> `6` parsed entries)
- **Investigation ID**: `k8s-inv-d69d5386`
- **Execution Latency**: `7.02 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.051` | Extracted pod=`order-processor-6d4f8b9a2-h5j8k`, namespace=`orders` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `6` lines (`1326` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `1` lines (`192` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`280` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.491` | Parsed `6` entries; levels=`{'INFO': 1, 'WARN': 3, 'ERROR': 2}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `5.153` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_SCHEDULING_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.022` | Primary RCA: `SCHEDULING_NODE_FAILURE` / `NODE_NOT_READY` (`CRITICAL`, conf=`0.97`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.022` | Pods=`['order-processor-6d4f8b9a2-h5j8k']`, NS=`['orders']`, Containers=`['order-consumer']`, Nodes=`['node-worker-11']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.024` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Worker Node NotReady / Kubelet PLEG Unhealthy
- **Causal Chain**:
  1. Container runtime (containerd/CRI) or Pod Lifecycle Event Generator (PLEG) became unresponsive on worker node
  1. Kubelet failed PLEG relist health check and stopped posting Ready status
  1. NodeController marked node NodeNotReady and initiated pod evictions

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Cordon and drain the unhealthy node to reschedule affected workloads onto healthy nodes.: `kubectl cordon node-worker-11 && kubectl drain node-worker-11 --ignore-daemonsets --delete-emptydir-data`
- **[PERMANENT_FIX]** Inspect kubelet and containerd daemon health on the affected worker node.: `kubectl describe node node-worker-11 | grep -A 12 'Conditions:'`

#### Ground-Truth Evaluation Checks
- **Category Match**: `SCHEDULING_NODE_FAILURE` == `SCHEDULING_NODE_FAILURE` (`True`)
- **Subtype Match**: `NODE_NOT_READY` == `NODE_NOT_READY` (`True`)
- **Severity Match**: `CRITICAL` == `CRITICAL` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['NodeNotReady', 'PLEG is not healthy', 'threshold is 3m0s', 'container runtime status check']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-07: Readiness Probe Misconfigured (Wrong HTTP Path / Port) (`trace-tc-07-readiness_probe_incorrect`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod catalog-search-7f8e9d6c4-b3n5m in namespace storefront"`
- **Source Log File**: `logs/tc07_readiness_probe_incorrect.log` (`6` lines -> `6` parsed entries)
- **Investigation ID**: `k8s-inv-9a2a1d30`
- **Execution Latency**: `7.72 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.054` | Extracted pod=`catalog-search-7f8e9d6c4-b3n5m`, namespace=`storefront` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `6` lines (`1490` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `3` lines (`774` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`283` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.625` | Parsed `6` entries; levels=`{'INFO': 2, 'WARN': 3, 'ERROR': 1}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `5.735` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_PROBE_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.032` | Primary RCA: `PROBE_FAILURE` (`HIGH`, conf=`0.95`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.025` | Pods=`['catalog-search-7f8e9d6c4-b3n5m']`, NS=`['storefront']`, Containers=`['catalog-service']`, Nodes=`['node-general-02']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.019` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Readiness Probe Failure Detected
- **Causal Chain**:
  1. Kubernetes Readiness probe failed (HTTP status: 404). Failing readiness probes cause the pod endpoint to be removed from Service load balancing, preventing traffic ingress.

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Inspect probe configuration and correct readiness/liveness path, port, or timeout.: `kubectl describe pod catalog-search-7f8e9d6c4-b3n5m | grep -A 10 -E 'Liveness|Readiness|Events'`

#### Ground-Truth Evaluation Checks
- **Category Match**: `PROBE_FAILURE` == `PROBE_FAILURE` (`True`)
- **Subtype Match**: `None` == `None` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `3/3` (`['Readiness probe failed', 'HTTP probe failed with statuscode: 404', '/healthz']`)
- **Remediation Commands Matched**: `1/1`

---

### TC-08: Resource Request Limits (Unschedulable Pod / Insufficient CPU & Memory) (`trace-tc-08-resource_request_limits`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod fraud-detection-model-9a8b7c6d5-p4l2k in namespace risk-engine"`
- **Source Log File**: `logs/tc08_resource_request_limits.log` (`4` lines -> `4` parsed entries)
- **Investigation ID**: `k8s-inv-304b5033`
- **Execution Latency**: `7.21 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.058` | Extracted pod=`fraud-detection-model-9a8b7c6d5-p4l2k`, namespace=`risk-engine` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `4` lines (`1273` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `2` lines (`659` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.003` | Fetched `8` lines (`307` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.346` | Parsed `4` entries; levels=`{'INFO': 1, 'WARN': 2, 'ERROR': 1}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `5.498` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_SCHEDULING_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.023` | Primary RCA: `SCHEDULING_NODE_FAILURE` / `INSUFFICIENT_CPU` (`HIGH`, conf=`0.96`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.019` | Pods=`['fraud-detection-model-9a8b7c6d5-p4l2k']`, NS=`['risk-engine']`, Containers=`['inference-server']`, Nodes=`['cluster-scheduler']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.019` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Kubernetes scheduler could not assign pod to any node (Resource starvation / Taints).
- **Causal Chain**:
  1. Pod created and submitted to kube-scheduler queue
  1. Scheduler filtering evaluated all candidate nodes
  1. 0 nodes satisfied CPU, memory, or taint requirements
  1. Pod stuck in Pending state

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Inspect node resource capacity and pod resource requests.: `kubectl describe nodes | grep -A 8 'Allocated resources'`
- **[PERMANENT_FIX]** Right-size excessive pod resource requests or scale out the worker node group.: `kubectl set resources deployment/<deployment-name> --requests=cpu=500m,memory=1Gi --limits=cpu=2000m,memory=2Gi`

#### Ground-Truth Evaluation Checks
- **Category Match**: `SCHEDULING_NODE_FAILURE` == `SCHEDULING_NODE_FAILURE` (`True`)
- **Subtype Match**: `INSUFFICIENT_CPU` == `INSUFFICIENT_CPU` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['FailedScheduling', '0/6 nodes are available', 'Insufficient cpu', 'Insufficient memory']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-09: Service Has No Endpoints (Label Selector Mismatch) (`trace-tc-09-service_no_endpoints`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod inventory-service-5c6d7e8f9-t2w4y in namespace fulfillment"`
- **Source Log File**: `logs/tc09_service_no_endpoints.log` (`5` lines -> `5` parsed entries)
- **Investigation ID**: `k8s-inv-9e9ea280`
- **Execution Latency**: `7.09 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.054` | Extracted pod=`inventory-service-5c6d7e8f9-t2w4y`, namespace=`fulfillment` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `5` lines (`1322` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `3` lines (`839` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.004` | Fetched `8` lines (`289` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.310` | Parsed `5` entries; levels=`{'INFO': 1, 'WARN': 1, 'ERROR': 3}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `5.151` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_NETWORK_DNS_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.050` | Primary RCA: `NETWORK_DNS_FAILURE` / `SERVICE_NO_ENDPOINTS` (`HIGH`, conf=`0.96`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.037` | Pods=`['inventory-service-5c6d7e8f9-t2w4y']`, NS=`['fulfillment']`, Containers=`['inventory-api']`, Nodes=`['node-general-05']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.035` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Kubernetes Service Has No Active Endpoints
- **Causal Chain**:
  1. Kubernetes Service selector evaluated pod labels in target namespace
  1. Zero running/ready pods matched the Service label selector (or targetPort mismatch)
  1. EndpointSlice controller published empty endpoint set (Endpoints: <none>)
  1. kube-proxy / ingress rejected traffic with 'no endpoints available for service' (HTTP 503)

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Compare Service label selector against pod labels and inspect Endpoints.: `kubectl get svc,endpoints,endpointslice -o wide && kubectl get pods --show-labels`
- **[PERMANENT_FIX]** Patch Service selector to match the Deployment pod template labels.: `kubectl patch svc <service-name> -p '{"spec":{"selector":{"app":"<app-label>"}}}'`

#### Ground-Truth Evaluation Checks
- **Category Match**: `NETWORK_DNS_FAILURE` == `NETWORK_DNS_FAILURE` (`True`)
- **Subtype Match**: `SERVICE_NO_ENDPOINTS` == `SERVICE_NO_ENDPOINTS` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `4/4` (`['no endpoints available for service', 'Endpoints: <none>', '0 active endpoints', 'selector mismatch']`)
- **Remediation Commands Matched**: `2/2`

---

### TC-10: Service Routes Traffic to Unhealthy Pods (publishNotReadyAddresses Enabled) (`trace-tc-10-service_routes_unhealthy_pods`)

- **Input Prompt**: `"Investigate the Kubernetes incident for pod checkout-gateway-4e5f6a7b8-r9m1c in namespace payments"`
- **Source Log File**: `logs/tc10_service_routes_unhealthy_pods.log` (`5` lines -> `5` parsed entries)
- **Investigation ID**: `k8s-inv-b12e1fb0`
- **Execution Latency**: `7.46 ms`

#### Agent Execution Step Trace

| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `target_extraction` | `KubernetesInvestigationAgent._extract_pod_target` | `SUCCESS` | `0.055` | Extracted pod=`checkout-gateway-4e5f6a7b8-r9m1c`, namespace=`payments` |
| 2 | `tool_call` | `get_pod_logs` | `SUCCESS` | `0.004` | Fetched `5` lines (`1426` chars) |
| 3 | `tool_call` | `get_pod_events` | `SUCCESS` | `0.002` | Fetched `1` lines (`341` chars) |
| 4 | `tool_call` | `get_deployment_history` | `SUCCESS` | `0.007` | Fetched `8` lines (`285` chars) |
| 5 | `log_parsing` | `LogParser.parse_text` | `SUCCESS` | `1.391` | Parsed `5` entries; levels=`{'WARN': 2, 'ERROR': 3}`; components=`[]` |
| 6 | `diagnostic_rule_evaluation` | `InvestigationEngine.rules` | `SUCCESS` | `5.625` | Evaluated `9` rules -> matched `1`: `['RULE_K8S_NETWORK_DNS_FAILURE']` |
| 7 | `causal_root_cause_resolution` | `InvestigationEngine._determine_root_cause` | `SUCCESS` | `0.026` | Primary RCA: `NETWORK_DNS_FAILURE` / `SERVICE_ROUTES_UNHEALTHY_PODS` (`HIGH`, conf=`0.95`) |
| 8 | `blast_radius_computation` | `InvestigationEngine._compute_blast_radius` | `SUCCESS` | `0.023` | Pods=`['checkout-gateway-4e5f6a7b8-r9m1c']`, NS=`['payments']`, Containers=`['checkout-proxy']`, Nodes=`['node-general-06']` |
| 9 | `remediation_generation` | `InvestigationEngine._generate_remediations` | `SUCCESS` | `0.023` | Generated `2` remediation actions |

#### Root Cause & Causal Chain
- **Root Cause Summary**: Service Routing Traffic to Unhealthy / Unready Pods
- **Causal Chain**:
  1. Backing pod failed readiness checks or entered unready state
  1. Service configured with publishNotReadyAddresses: true (or missing readiness gate enforcement)
  1. EndpointSlice continued advertising unready pod IP as an active backend
  1. Service/Ingress routed live client requests to unhealthy pod, causing HTTP 502/503 errors

#### Generated Remediation Commands
- **[IMMEDIATE_MITIGATION]** Disable publishNotReadyAddresses on the Service so unready pods are excluded from load balancing.: `kubectl patch svc <service-name> -p '{"spec":{"publishNotReadyAddresses":false}}'`
- **[PERMANENT_FIX]** Configure a strict readinessProbe verifying application dependency health.: `kubectl get endpointslice -o wide && kubectl describe pod checkout-gateway-4e5f6a7b8-r9m1c`

#### Ground-Truth Evaluation Checks
- **Category Match**: `NETWORK_DNS_FAILURE` == `NETWORK_DNS_FAILURE` (`True`)
- **Subtype Match**: `SERVICE_ROUTES_UNHEALTHY_PODS` == `SERVICE_ROUTES_UNHEALTHY_PODS` (`True`)
- **Severity Match**: `HIGH` == `HIGH` (`True`)
- **Blast Radius Match**: `True`
- **Evidence Keywords Matched**: `3/3` (`['publishNotReadyAddresses: true', 'routing live traffic to unready pod', 'unready endpoint']`)
- **Remediation Commands Matched**: `2/2`

---
