# 🏆 Kubernetes Investigation Agent — Trace Evaluation Scorecard

## 1. Overall Benchmark Grade

| Metric | Value |
| :--- | :--- |
| **Benchmark Dataset** | `K8s-Investigation-Agent Incident Evaluation Benchmark` (`v1.0.0`) |
| **Overall Score** | **`1000.0 / 1000.0` (`100.0%`)** |
| **Overall Letter Grade** | **`A+`** |
| **Test Cases Passed** | **`10 / 10` (`100.0%`)** |
| **Average Execution Latency** | `9.27 ms` / case |

## 2. Rubric Dimension Breakdown

| Dimension | Weight (Max Pts) | Avg Score | Score % | Status |
| :--- | :---: | :---: | :---: | :---: |
| **D1: Tool & Step Trajectory** | `15` | `15.0 / 15` | `100.0%` | **PASS** |
| **D2: Root Cause Accuracy (Category + Subtype)** | `25` | `25.0 / 25` | `100.0%` | **PASS** |
| **D3: Severity & Confidence Calibration** | `10` | `10.0 / 10` | `100.0%` | **PASS** |
| **D4: Evidence Grounding & Causal Chain** | `20` | `20.0 / 20` | `100.0%` | **PASS** |
| **D5: Blast Radius (Pod/NS/Container/Node)** | `15` | `15.0 / 15` | `100.0%` | **PASS** |
| **D6: Actionable Remediation Quality** | `15` | `15.0 / 15` | `100.0%` | **PASS** |

## 3. Per-Test-Case Trace Scorecard (`TC-01` – `TC-10`)

| Case ID | Incident Scenario | D1: Trajectory (`15`) | D2: RCA (`25`) | D3: Severity (`10`) | D4: Evidence (`20`) | D5: Blast Radius (`15`) | D6: Remediation (`15`) | Total (`100`) | Grade | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-01** | OOM Kill (Container Memory Limit Exceeded) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-02** | CPU Throttling (CFS Quota Exhaustion) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-03** | Container Crash (Unhandled Runtime Panic / SIGSEGV) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-04** | CrashLoopBackOff (Missing Secret / Startup Configuration Failure) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-05** | Node Memory Pressure & Kubelet Pod Eviction | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-06** | Node Not Ready (PLEG Unhealthy & Container Runtime Hang) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-07** | Readiness Probe Misconfigured (Wrong HTTP Path / Port) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-08** | Resource Request Limits (Unschedulable Pod / Insufficient CPU & Memory) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-09** | Service Has No Endpoints (Label Selector Mismatch) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |
| **TC-10** | Service Routes Traffic to Unhealthy Pods (publishNotReadyAddresses Enabled) | `15/15` | `25/25` | `10/10` | `20/20` | `15/15` | `15/15` | **`100/100`** | **`A+`** | **PASS** |

## 4. Detailed Verification Matrix by Test Case

| Case ID | Target Extracted | Tools Invoked | Parsed Lines | Root Cause (`Subtype`) | Severity (`Conf`) | Evidence Keywords | Blast Radius (`Pod`/`NS`/`Container`/`Node`) | Remediation Cmds | Latency |
| :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- | :---: | :---: |
| **TC-01** | `True` | `3/3` | `9/9` | `OOM_KILL` | `CRITICAL` (`98%`) | `4/4` | `4/4` (`node-gpu-pool-02`) | `2/2` | `16.37 ms` |
| **TC-02** | `True` | `3/3` | `6/6` | `SCHEDULING_NODE_FAILURE` (`CPU_THROTTLING`) | `HIGH` (`94%`) | `4/4` | `4/4` (`node-general-04`) | `2/2` | `8.36 ms` |
| **TC-03** | `True` | `3/3` | `8/8` | `APPLICATION_PANIC` | `HIGH` (`90%`) | `4/4` | `4/4` (`node-general-01`) | `2/2` | `10.46 ms` |
| **TC-04** | `True` | `3/3` | `9/9` | `CRASH_LOOP` | `CRITICAL` (`95%`) | `4/4` | `4/4` (`node-general-03`) | `2/2` | `13.02 ms` |
| **TC-05** | `True` | `3/3` | `6/6` | `SCHEDULING_NODE_FAILURE` (`NODE_MEMORY_PRESSURE`) | `CRITICAL` (`96%`) | `4/4` | `4/4` (`node-worker-07`) | `2/2` | `7.99 ms` |
| **TC-06** | `True` | `3/3` | `6/6` | `SCHEDULING_NODE_FAILURE` (`NODE_NOT_READY`) | `CRITICAL` (`97%`) | `4/4` | `4/4` (`node-worker-11`) | `2/2` | `7.02 ms` |
| **TC-07** | `True` | `3/3` | `6/6` | `PROBE_FAILURE` | `HIGH` (`95%`) | `3/3` | `4/4` (`node-general-02`) | `1/1` | `7.72 ms` |
| **TC-08** | `True` | `3/3` | `4/4` | `SCHEDULING_NODE_FAILURE` (`INSUFFICIENT_CPU`) | `HIGH` (`96%`) | `4/4` | `4/4` (`cluster-scheduler`) | `2/2` | `7.21 ms` |
| **TC-09** | `True` | `3/3` | `5/5` | `NETWORK_DNS_FAILURE` (`SERVICE_NO_ENDPOINTS`) | `HIGH` (`96%`) | `4/4` | `4/4` (`node-general-05`) | `2/2` | `7.09 ms` |
| **TC-10** | `True` | `3/3` | `5/5` | `NETWORK_DNS_FAILURE` (`SERVICE_ROUTES_UNHEALTHY_PODS`) | `HIGH` (`95%`) | `3/3` | `4/4` (`node-general-06`) | `2/2` | `7.46 ms` |
