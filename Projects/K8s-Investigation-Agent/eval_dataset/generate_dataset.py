"""Synthesizes 10 realistic Kubernetes incident test cases for the evaluation dataset."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"


TEST_CASES = [
    {
        "id": "TC-01",
        "slug": "oom_kill",
        "name": "OOM Kill (Container Memory Limit Exceeded)",
        "log_file": "logs/tc01_oom_kill.log",
        "scenario_description": (
            "An ML recommendation worker container ('recommendation-worker') in pod "
            "'recommendation-engine-6b8f9c4d2-x7v2p' (namespace 'ml-serving') loads a dense "
            "vector embedding index during a traffic spike, exceeding its 512Mi cgroup memory limit. "
            "The Linux kernel OOM killer dispatches SIGKILL (exit code 137), and kubelet marks the "
            "container OOMKilled before entering CrashLoopBackOff."
        ),
        "injected_fault": "Container memory allocation (548Mi) exceeds resources.limits.memory (512Mi), triggering kernel cgroup OOM killer (SIGKILL / exit code 137).",
        "expected_root_cause_category": "OOM_KILL",
        "expected_severity": "CRITICAL",
        "expected_impacted_resources": ["recommendation-engine-6b8f9c4d2-x7v2p"],
        "expected_namespace": "ml-serving",
        "expected_container": "recommendation-worker",
        "expected_node": "node-gpu-pool-02",
        "ground_truth_rca": (
            "Container 'recommendation-worker' in pod 'recommendation-engine-6b8f9c4d2-x7v2p' was terminated "
            "by the Linux kernel Out-Of-Memory (OOM) killer with exit code 137 (SIGKILL) after exceeding its "
            "512Mi cgroup memory limit, triggering repeated CrashLoopBackOff restarts."
        ),
        "ground_truth_evidence_keywords": [
            "OOMKilled",
            "Memory cgroup out of memory: Killed process",
            "exit code 137",
            "CrashLoopBackOff",
        ],
        "expected_remediation_commands": [
            "kubectl set resources deployment/<deployment-name> --limits=memory=1Gi --requests=memory=512Mi",
            "kubectl logs recommendation-engine-6b8f9c4d2-x7v2p --previous | grep -i -E 'oom|memory|heap'",
        ],
        "log_content": """2026-10-14T08:10:01.112Z INFO pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 Starting recommendation-worker v2.4.1 (limits.memory=512Mi, requests.memory=256Mi)
2026-10-14T08:10:04.340Z INFO pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 Loading user-item embedding shard-04 into in-memory FAISS index (estimated size: 420MB)
2026-10-14T08:10:09.812Z WARN pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 High batch inference concurrency (64 concurrent requests); heap usage at 498Mi / 512Mi (97.2%)
2026-10-14T08:10:11.004Z ERROR pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 kernel: Memory cgroup out of memory: Killed process 4182 (python3) total-vm:1428492kB, anon-rss:524188kB, file-rss:1420kB, shmem-rss:0kB, UID:1000
2026-10-14T08:10:11.019Z ERROR pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 kernel: oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=cri-containerd-9a8b7c.scope,mems_allowed=0,oom_memcg=/kubepods.slice/kubepods-burstable.slice,task_memcg=/kubepods.slice,task=python3,pid=4182,uid=1000
2026-10-14T08:10:11.450Z WARN pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 kubelet: Container recommendation-worker in pod recommendation-engine-6b8f9c4d2-x7v2p terminated with exit code 137 (Reason: OOMKilled, Signal: 9)
2026-10-14T08:10:12.100Z WARN pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 Last State: Terminated (Reason: OOMKilled, Exit Code: 137)
2026-10-14T08:10:25.600Z WARN pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 Normal Pulled: Container image "registry.internal/ml/recommendation-worker:v2.4.1" already present on machine
2026-10-14T08:10:31.900Z ERROR pod=recommendation-engine-6b8f9c4d2-x7v2p namespace=ml-serving container=recommendation-worker node=node-gpu-pool-02 Warning BackOff: Back-off restarting failed container recommendation-worker in pod recommendation-engine-6b8f9c4d2-x7v2p_ml-serving (CrashLoopBackOff)
""",
    },
    {
        "id": "TC-02",
        "slug": "cpu_throttling",
        "name": "CPU Throttling (CFS Quota Exhaustion)",
        "log_file": "logs/tc02_cpu_throttling.log",
        "scenario_description": (
            "A latency-sensitive pricing API ('pricing-api') in pod 'pricing-calculator-7c9d4b5f8-m2k9l' "
            "(namespace 'commerce') runs 8 OS worker threads with a restrictive CPU limit of 200m "
            "(cfs_quota_us=20000 per 100000us period). During promotional traffic bursts, the Linux CFS "
            "bandwidth controller throttles the container across 86.4% of scheduling periods, spiking p99 "
            "response times to 2.45s without killing the container."
        ),
        "injected_fault": "Restrictive resources.limits.cpu: 200m on multi-threaded Go service (GOMAXPROCS=8) causing severe Linux CFS bandwidth throttling.",
        "expected_root_cause_category": "SCHEDULING_NODE_FAILURE",
        "expected_subtype": "CPU_THROTTLING",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["pricing-calculator-7c9d4b5f8-m2k9l"],
        "expected_namespace": "commerce",
        "expected_container": "pricing-api",
        "expected_node": "node-general-04",
        "ground_truth_rca": (
            "Container 'pricing-api' in pod 'pricing-calculator-7c9d4b5f8-m2k9l' is experiencing severe "
            "Linux CFS CPU bandwidth throttling (nr_throttled=412, throttled_time=38.42s, 86.4% periods throttled) "
            "because its 8 concurrent worker threads rapidly exhaust the 200m CPU quota within each 100ms period."
        ),
        "ground_truth_evidence_keywords": [
            "CPU throttling detected",
            "nr_throttled=412",
            "throttled_time=",
            "CFS quota exceeded",
        ],
        "expected_remediation_commands": [
            "kubectl set resources deployment/<deployment-name> --limits=cpu=2000m --requests=cpu=500m",
            "kubectl top pod pricing-calculator-7c9d4b5f8-m2k9l --containers",
        ],
        "log_content": """2026-10-14T09:14:02.015Z INFO pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 Starting pricing-api v1.18.0 with GOMAXPROCS=8 (resources.requests.cpu=100m, resources.limits.cpu=200m)
2026-10-14T09:14:15.220Z INFO pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 Incoming flash-sale traffic burst: 420 req/sec on /api/v2/calculate-quote
2026-10-14T09:14:22.480Z WARN pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 cadvisor: CPU throttling detected: container pricing-api throttled in 86.4% of CFS periods (cpu.cfs_quota_us=20000, cpu.cfs_period_us=100000)
2026-10-14T09:14:25.105Z WARN pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 cgroup/cpu.stat: nr_periods=477 nr_throttled=412 throttled_time=38420000000
2026-10-14T09:14:28.912Z ERROR pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 kubelet: CFS quota exceeded for container pricing-api: runnable threads stalled for 820ms waiting for next CFS bandwidth period
2026-10-14T09:14:30.330Z WARN pod=pricing-calculator-7c9d4b5f8-m2k9l namespace=commerce container=pricing-api node=node-general-04 HTTP request latency degradation: p50=410ms p95=1890ms p99=2450ms (SLO threshold: 250ms) due to CPU CFS throttling
""",
    },
    {
        "id": "TC-03",
        "slug": "container_crash",
        "name": "Container Crash (Unhandled Runtime Panic / SIGSEGV)",
        "log_file": "logs/tc03_container_crash.log",
        "scenario_description": (
            "An invoice batch worker container ('invoice-worker') in pod 'invoice-generator-5f7b8d9c1-q4n8w' "
            "(namespace 'billing') crashes mid-execution due to an unhandled nil pointer dereference "
            "(SIGSEGV) when processing an invoice record with a null tax jurisdiction object. The container "
            "terminates immediately with exit code 2."
        ),
        "injected_fault": "Null tax_jurisdiction struct dereferenced in CalculateRegionalTax(), triggering Go runtime SIGSEGV panic and container exit code 2.",
        "expected_root_cause_category": "APPLICATION_PANIC",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["invoice-generator-5f7b8d9c1-q4n8w"],
        "expected_namespace": "billing",
        "expected_container": "invoice-worker",
        "expected_node": "node-general-01",
        "ground_truth_rca": (
            "Container 'invoice-worker' in pod 'invoice-generator-5f7b8d9c1-q4n8w' crashed with exit code 2 "
            "due to an unhandled Go runtime nil pointer dereference panic (SIGSEGV) in "
            "billing/tax.CalculateRegionalTax() at invoice_processor.go:142."
        ),
        "ground_truth_evidence_keywords": [
            "panic: runtime error: invalid memory address or nil pointer dereference",
            "SIGSEGV",
            "goroutine",
            "exit code 2",
        ],
        "expected_remediation_commands": [
            "kubectl logs invoice-generator-5f7b8d9c1-q4n8w --previous",
            "kubectl describe pod invoice-generator-5f7b8d9c1-q4n8w",
        ],
        "log_content": """2026-10-14T10:05:00.120Z INFO pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 Starting invoice-worker v3.1.2 batch job (batch_id=INV-2026-10-14-A)
2026-10-14T10:05:03.410Z INFO pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 Processed 140/500 invoices in batch INV-2026-10-14-A
2026-10-14T10:05:04.892Z WARN pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 Invoice record id=inv_994821 has empty tax_jurisdiction metadata; proceeding with default rate lookup
2026-10-14T10:05:04.895Z FATAL pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 panic: runtime error: invalid memory address or nil pointer dereference
2026-10-14T10:05:04.895Z ERROR pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 [signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x7f4a2b]
2026-10-14T10:05:04.896Z ERROR pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 goroutine 42 [running]:
2026-10-14T10:05:04.896Z ERROR pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 github.com/acme/billing/internal/tax.CalculateRegionalTax(0x0, 0xc000214800) /app/internal/tax/invoice_processor.go:142 +0x5b
2026-10-14T10:05:05.210Z ERROR pod=invoice-generator-5f7b8d9c1-q4n8w namespace=billing container=invoice-worker node=node-general-01 kubelet: Container invoice-worker terminated with exit code 2 (Reason: Error)
""",
    },
    {
        "id": "TC-04",
        "slug": "crash_loop_backoff",
        "name": "CrashLoopBackOff (Missing Secret / Startup Configuration Failure)",
        "log_file": "logs/tc04_crash_loop_backoff.log",
        "scenario_description": (
            "The authentication service pod 'auth-token-service-84d9b6c7f-z9p3x' (container 'auth-server', "
            "namespace 'identity') fails on startup because the required RSA private key file "
            "'/etc/secrets/jwt/private.pem' is missing from its mounted Secret volume. The process exits "
            "with code 1 on every boot attempt, causing kubelet to place the pod into CrashLoopBackOff "
            "after 6 rapid restarts."
        ),
        "injected_fault": "Missing '/etc/secrets/jwt/private.pem' key in mounted Kubernetes Secret causes immediate startup exit (code 1) and exponential CrashLoopBackOff.",
        "expected_root_cause_category": "CRASH_LOOP",
        "expected_severity": "CRITICAL",
        "expected_impacted_resources": ["auth-token-service-84d9b6c7f-z9p3x"],
        "expected_namespace": "identity",
        "expected_container": "auth-server",
        "expected_node": "node-general-03",
        "ground_truth_rca": (
            "Container 'auth-server' in pod 'auth-token-service-84d9b6c7f-z9p3x' is stuck in CrashLoopBackOff "
            "(restartCount=6, exit code 1) because it cannot load the required JWT signing key at "
            "'/etc/secrets/jwt/private.pem' during initialization."
        ),
        "ground_truth_evidence_keywords": [
            "CrashLoopBackOff",
            "Back-off restarting failed container",
            "exit code 1",
            "/etc/secrets/jwt/private.pem",
        ],
        "expected_remediation_commands": [
            "kubectl logs auth-token-service-84d9b6c7f-z9p3x --previous",
            "kubectl debug -it auth-token-service-84d9b6c7f-z9p3x --image=busybox --target=app",
        ],
        "log_content": """2026-10-14T11:20:01.050Z INFO pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 Initializing auth-server v4.0.1 (env=production)
2026-10-14T11:20:01.180Z ERROR pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 ConfigError: Failed to load RSA signing key from /etc/secrets/jwt/private.pem: open /etc/secrets/jwt/private.pem: no such file or directory
2026-10-14T11:20:01.185Z ERROR pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 Startup validation failed; exiting with status 1
2026-10-14T11:20:01.520Z WARN pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 kubelet: Container auth-server terminated with exit code 1 (restartCount=5)
2026-10-14T11:21:25.900Z WARN pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 kubelet: Restarting failed container auth-server in pod auth-token-service-84d9b6c7f-z9p3x_identity (restartCount=6)
2026-10-14T11:21:26.110Z ERROR pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 ConfigError: Failed to load RSA signing key from /etc/secrets/jwt/private.pem: open /etc/secrets/jwt/private.pem: no such file or directory
2026-10-14T11:21:26.400Z WARN pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 kubelet: Container auth-server exited with exit code 1
2026-10-14T11:21:27.010Z ERROR pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 Warning BackOff: Back-off restarting failed container auth-server in pod auth-token-service-84d9b6c7f-z9p3x_identity(8f2a1c9d-4e3b-4a11-9c22-7b6d5e4f3a21)
2026-10-14T11:21:27.015Z ERROR pod=auth-token-service-84d9b6c7f-z9p3x namespace=identity container=auth-server node=node-general-03 State: Waiting, Reason: CrashLoopBackOff (Last State: Terminated, Exit Code: 1, Restart Count: 6)
""",
    },
    {
        "id": "TC-05",
        "slug": "node_memory_pressure",
        "name": "Node Memory Pressure & Kubelet Pod Eviction",
        "log_file": "logs/tc05_node_memory_pressure.log",
        "scenario_description": (
            "Worker node 'node-worker-07' runs critically low on host memory (available RAM drops to 42Mi, "
            "below the 100Mi eviction hard threshold). Kubelet transitions node condition 'MemoryPressure' "
            "to True and invokes the eviction manager to evict Burstable pod "
            "'analytics-aggregator-59b7c4d8e-v6r2t' (container 'spark-executor', namespace 'data-pipeline')."
        ),
        "injected_fault": "Host node available memory falls below kubelet evictionHard threshold (memory.available<100Mi), triggering NodeCondition MemoryPressure=True and pod eviction.",
        "expected_root_cause_category": "SCHEDULING_NODE_FAILURE",
        "expected_subtype": "NODE_MEMORY_PRESSURE",
        "expected_severity": "CRITICAL",
        "expected_impacted_resources": ["analytics-aggregator-59b7c4d8e-v6r2t"],
        "expected_namespace": "data-pipeline",
        "expected_container": "spark-executor",
        "expected_node": "node-worker-07",
        "ground_truth_rca": (
            "Worker node 'node-worker-07' entered MemoryPressure=True when available host memory dropped to "
            "42Mi (below the 100Mi eviction threshold), causing the kubelet eviction manager to evict pod "
            "'analytics-aggregator-59b7c4d8e-v6r2t'."
        ),
        "ground_truth_evidence_keywords": [
            "MemoryPressure",
            "The node was low on resource: memory",
            "Evicted",
            "NodeHasInsufficientMemory",
        ],
        "expected_remediation_commands": [
            "kubectl describe node node-worker-07 | grep -A 15 -E 'Conditions:|Allocated resources:'",
            "kubectl get pods -A --field-selector=status.phase=Failed -o wide",
        ],
        "log_content": """2026-10-14T12:30:10.100Z INFO pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 Executing shuffle stage 14 across 32 partitions (RSS memory=6.8Gi, requests.memory=2Gi)
2026-10-14T12:30:18.420Z WARN pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 kubelet: NodeHasInsufficientMemory: Node node-worker-07 status is now: NodeHasInsufficientMemory
2026-10-14T12:30:18.450Z WARN pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 kubelet: NodeCondition MemoryPressure transitioned to status=True (reason=KubeletHasInsufficientMemory, message="kubelet has insufficient memory available")
2026-10-14T12:30:19.110Z ERROR pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 eviction_manager: attempting to reclaim memory; memory.available=42Mi is below eviction threshold 100Mi
2026-10-14T12:30:19.890Z ERROR pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 Warning Evicted: The node was low on resource: memory. Threshold quantity: 100Mi, available: 42Mi. Container spark-executor was using 6982Mi, request is 2048Mi, has larger consumption of memory.
2026-10-14T12:30:20.300Z WARN pod=analytics-aggregator-59b7c4d8e-v6r2t namespace=data-pipeline container=spark-executor node=node-worker-07 Normal Killing: Stopping container spark-executor due to kubelet node memory pressure eviction
""",
    },
    {
        "id": "TC-06",
        "slug": "node_not_ready",
        "name": "Node Not Ready (PLEG Unhealthy & Container Runtime Hang)",
        "log_file": "logs/tc06_node_not_ready.log",
        "scenario_description": (
            "Worker node 'node-worker-11' hosting pod 'order-processor-6d4f8b9a2-h5j8k' (container "
            "'order-consumer', namespace 'orders') suffers a containerd runtime deadlock. Kubelet's Pod "
            "Lifecycle Event Generator (PLEG) fails relist health checks after exceeding the 3m0s timeout "
            "(last seen active 4m12s ago). The node transitions to NodeNotReady and the node controller "
            "initiates pod eviction."
        ),
        "injected_fault": "containerd CRI socket deadlock on node-worker-11 causes kubelet PLEG relist timeout (>3m0s) and NodeNotReady state transition.",
        "expected_root_cause_category": "SCHEDULING_NODE_FAILURE",
        "expected_subtype": "NODE_NOT_READY",
        "expected_severity": "CRITICAL",
        "expected_impacted_resources": ["order-processor-6d4f8b9a2-h5j8k"],
        "expected_namespace": "orders",
        "expected_container": "order-consumer",
        "expected_node": "node-worker-11",
        "ground_truth_rca": (
            "Worker node 'node-worker-11' transitioned to NodeNotReady because the kubelet Pod Lifecycle Event "
            "Generator (PLEG) became unhealthy ('pleg was last seen active 4m12s ago; threshold is 3m0s') due "
            "to an unresponsive containerd CRI runtime socket, disrupting pod 'order-processor-6d4f8b9a2-h5j8k'."
        ),
        "ground_truth_evidence_keywords": [
            "NodeNotReady",
            "PLEG is not healthy",
            "threshold is 3m0s",
            "container runtime status check",
        ],
        "expected_remediation_commands": [
            "kubectl cordon node-worker-11 && kubectl drain node-worker-11 --ignore-daemonsets --delete-emptydir-data",
            "kubectl describe node node-worker-11 | grep -A 12 'Conditions:'",
        ],
        "log_content": """2026-10-14T13:40:05.200Z INFO pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 Consuming order events from partition orders-topic-02
2026-10-14T13:43:50.112Z WARN pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 kubelet: GenericPLEG: relisting pods timed out waiting for containerd CRI ListPodSandbox response
2026-10-14T13:44:18.640Z ERROR pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 kubelet: PLEG is not healthy: pleg was last seen active 4m12s ago; threshold is 3m0s
2026-10-14T13:44:19.005Z ERROR pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 kubelet: KubeletNotReady: container runtime status check may not have completed yet; PLEG is not healthy
2026-10-14T13:44:22.310Z WARN pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 node-controller: Node node-worker-11 status is now: NodeNotReady
2026-10-14T13:44:55.800Z WARN pod=order-processor-6d4f8b9a2-h5j8k namespace=orders container=order-consumer node=node-worker-11 node-lifecycle-controller: Marking pod order-processor-6d4f8b9a2-h5j8k for taint-based eviction due to node.kubernetes.io/not-ready on node-worker-11
""",
    },
    {
        "id": "TC-07",
        "slug": "readiness_probe_incorrect",
        "name": "Readiness Probe Misconfigured (Wrong HTTP Path / Port)",
        "log_file": "logs/tc07_readiness_probe_incorrect.log",
        "scenario_description": (
            "The catalog search service ('catalog-service') in pod 'catalog-search-7f8e9d6c4-b3n5m' "
            "(namespace 'storefront') initializes cleanly and serves traffic on port 8080 with health check "
            "endpoint '/api/v1/healthz'. However, the Deployment's readinessProbe is misconfigured to query "
            "'http://10.244.2.48:8080/healthz', which returns HTTP 404 Not Found. Kubelet marks the pod "
            "Unhealthy (0/1 Ready) without restarting the container."
        ),
        "injected_fault": "Deployment spec.template.spec.containers[0].readinessProbe.httpGet.path set to '/healthz' instead of '/api/v1/healthz', returning HTTP 404.",
        "expected_root_cause_category": "PROBE_FAILURE",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["catalog-search-7f8e9d6c4-b3n5m"],
        "expected_namespace": "storefront",
        "expected_container": "catalog-service",
        "expected_node": "node-general-02",
        "ground_truth_rca": (
            "Pod 'catalog-search-7f8e9d6c4-b3n5m' (container 'catalog-service') is marked Unready because its "
            "Kubernetes readinessProbe is querying '/healthz' (returning HTTP 404 Not Found) instead of the "
            "application's actual health endpoint '/api/v1/healthz'."
        ),
        "ground_truth_evidence_keywords": [
            "Readiness probe failed",
            "HTTP probe failed with statuscode: 404",
            "/healthz",
        ],
        "expected_remediation_commands": [
            "kubectl describe pod catalog-search-7f8e9d6c4-b3n5m | grep -A 10 -E 'Liveness|Readiness|Events'",
        ],
        "log_content": """2026-10-14T14:15:01.080Z INFO pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 Starting catalog-service v2.9.0; HTTP server listening on 0.0.0.0:8080 (health endpoint registered at /api/v1/healthz)
2026-10-14T14:15:03.420Z INFO pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 Connected to Elasticsearch cluster and Redis cache; application ready to serve requests
2026-10-14T14:15:10.115Z WARN pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 GET /healthz HTTP/1.1 404 Not Found (user-agent: kube-probe/1.29) - route not registered, use /api/v1/healthz
2026-10-14T14:15:10.120Z WARN pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 Warning Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 404 (GET http://10.244.2.48:8080/healthz)
2026-10-14T14:15:20.118Z WARN pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 Warning Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 404 (GET http://10.244.2.48:8080/healthz)
2026-10-14T14:15:30.122Z ERROR pod=catalog-search-7f8e9d6c4-b3n5m namespace=storefront container=catalog-service node=node-general-02 Warning Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 404 (x3 over 20s); pod marked 0/1 Ready (restartCount=0)
""",
    },
    {
        "id": "TC-08",
        "slug": "resource_request_limits",
        "name": "Resource Request Limits (Unschedulable Pod / Insufficient CPU & Memory)",
        "log_file": "logs/tc08_resource_request_limits.log",
        "scenario_description": (
            "Pod 'fraud-detection-model-9a8b7c6d5-p4l2k' (container 'inference-server', namespace 'risk-engine') "
            "is deployed with excessive resource requests (requests.cpu=16000m, requests.memory=64Gi) on a "
            "6-node cluster of 8-vCPU / 32Gi worker nodes. The Kubernetes scheduler rejects all candidate "
            "nodes with FailedScheduling ('0/6 nodes are available: 4 Insufficient cpu, 6 Insufficient memory'), "
            "leaving the pod stuck in Pending."
        ),
        "injected_fault": "Oversized pod resource requests (cpu: 16, memory: 64Gi) exceed maximum single-node allocatable capacity (8 vCPU, 32Gi).",
        "expected_root_cause_category": "SCHEDULING_NODE_FAILURE",
        "expected_subtype": "INSUFFICIENT_CPU",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["fraud-detection-model-9a8b7c6d5-p4l2k"],
        "expected_namespace": "risk-engine",
        "expected_container": "inference-server",
        "expected_node": "cluster-scheduler",
        "ground_truth_rca": (
            "Pod 'fraud-detection-model-9a8b7c6d5-p4l2k' is stuck in Pending state because its container "
            "resource requests (16 CPU cores, 64Gi RAM) exceed the allocatable capacity of all 6 worker nodes "
            "('0/6 nodes are available: 4 Insufficient cpu, 6 Insufficient memory')."
        ),
        "ground_truth_evidence_keywords": [
            "FailedScheduling",
            "0/6 nodes are available",
            "Insufficient cpu",
            "Insufficient memory",
        ],
        "expected_remediation_commands": [
            "kubectl describe nodes | grep -A 8 'Allocated resources'",
            "kubectl set resources deployment/<deployment-name> --requests=cpu=500m,memory=1Gi --limits=cpu=2000m,memory=2Gi",
        ],
        "log_content": """2026-10-14T15:02:01.010Z INFO pod=fraud-detection-model-9a8b7c6d5-p4l2k namespace=risk-engine container=inference-server node=cluster-scheduler ReplicaSet fraud-detection-model-9a8b7c6d5 created pod fraud-detection-model-9a8b7c6d5-p4l2k (requests: cpu=16000m, memory=64Gi; limits: cpu=32000m, memory=128Gi)
2026-10-14T15:02:01.240Z WARN pod=fraud-detection-model-9a8b7c6d5-p4l2k namespace=risk-engine container=inference-server node=cluster-scheduler Warning FailedScheduling: 0/6 nodes are available: 4 Insufficient cpu, 6 Insufficient memory. preemption: 0/6 nodes are available: 6 No preemption victims found for incoming pod.
2026-10-14T15:02:15.510Z ERROR pod=fraud-detection-model-9a8b7c6d5-p4l2k namespace=risk-engine container=inference-server node=cluster-scheduler default-scheduler: Pod fraud-detection-model-9a8b7c6d5-p4l2k remains Pending (node allocatable max: cpu=7800m, memory=29.4Gi; requested: cpu=16000m, memory=64Gi)
2026-10-14T15:02:45.890Z WARN pod=fraud-detection-model-9a8b7c6d5-p4l2k namespace=risk-engine container=inference-server node=cluster-scheduler Warning FailedScheduling: 0/6 nodes are available: 4 Insufficient cpu, 6 Insufficient memory. preemption: 0/6 nodes are available: 6 No preemption victims found for incoming pod. (x3 over 45s)
""",
    },
    {
        "id": "TC-09",
        "slug": "service_no_endpoints",
        "name": "Service Has No Endpoints (Label Selector Mismatch)",
        "log_file": "logs/tc09_service_no_endpoints.log",
        "scenario_description": (
            "Kubernetes Service 'inventory-svc' in namespace 'fulfillment' is configured with label selector "
            "'app=inventory-backend,tier=api', while the running Deployment pod 'inventory-service-5c6d7e8f9-t2w4y' "
            "(container 'inventory-api') has labels 'app=inventory-service,tier=backend'. Because zero pods "
            "match the selector, the Service's Endpoints object is empty ('Endpoints: <none>') and ingress "
            "requests fail with 'no endpoints available for service inventory-svc' (HTTP 503)."
        ),
        "injected_fault": "Label selector mismatch between Service 'inventory-svc' (app=inventory-backend) and Deployment pods (app=inventory-service) results in 0 active Service endpoints.",
        "expected_root_cause_category": "NETWORK_DNS_FAILURE",
        "expected_subtype": "SERVICE_NO_ENDPOINTS",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["inventory-service-5c6d7e8f9-t2w4y"],
        "expected_namespace": "fulfillment",
        "expected_container": "inventory-api",
        "expected_node": "node-general-05",
        "ground_truth_rca": (
            "Kubernetes Service 'inventory-svc' in namespace 'fulfillment' has zero active endpoints "
            "('Endpoints: <none>', 'no endpoints available for service \"inventory-svc\"') due to a label "
            "selector mismatch ('app=inventory-backend,tier=api') against pod "
            "'inventory-service-5c6d7e8f9-t2w4y' ('app=inventory-service,tier=backend')."
        ),
        "ground_truth_evidence_keywords": [
            "no endpoints available for service",
            "Endpoints: <none>",
            "0 active endpoints",
            "selector mismatch",
        ],
        "expected_remediation_commands": [
            "kubectl get svc,endpoints,endpointslice -o wide && kubectl get pods --show-labels",
            "kubectl patch svc <service-name> -p '{\"spec\":{\"selector\":{\"app\":\"<app-label>\"}}}'",
        ],
        "log_content": """2026-10-14T16:10:02.110Z INFO pod=inventory-service-5c6d7e8f9-t2w4y namespace=fulfillment container=inventory-api node=node-general-05 Pod inventory-service-5c6d7e8f9-t2w4y is Running (1/1 Ready) with labels: app=inventory-service,tier=backend
2026-10-14T16:10:05.300Z WARN pod=inventory-service-5c6d7e8f9-t2w4y namespace=fulfillment container=inventory-api node=node-general-05 endpointslice-controller: Service fulfillment/inventory-svc selector (app=inventory-backend,tier=api) matched 0 pods; selector mismatch detected against deployment inventory-service
2026-10-14T16:10:05.315Z ERROR pod=inventory-service-5c6d7e8f9-t2w4y namespace=fulfillment container=inventory-api node=node-general-05 endpointslice-controller: Service inventory-svc has 0 active endpoints (Endpoints: <none>)
2026-10-14T16:10:12.780Z ERROR pod=inventory-service-5c6d7e8f9-t2w4y namespace=fulfillment container=inventory-api node=node-general-05 ingress-nginx: connect() failed: no endpoints available for service "inventory-svc" while routing GET /api/v1/stock -> HTTP 503 Service Temporarily Unavailable
2026-10-14T16:10:18.920Z ERROR pod=inventory-service-5c6d7e8f9-t2w4y namespace=fulfillment container=inventory-api node=node-general-05 kube-proxy: rejecting packet for service fulfillment/inventory-svc:80: service has no active endpoints
""",
    },
    {
        "id": "TC-10",
        "slug": "service_routes_unhealthy_pods",
        "name": "Service Routes Traffic to Unhealthy Pods (publishNotReadyAddresses Enabled)",
        "log_file": "logs/tc10_service_routes_unhealthy_pods.log",
        "scenario_description": (
            "Pod 'checkout-gateway-4e5f6a7b8-r9m1c' (container 'checkout-proxy', namespace 'payments') is "
            "failing its readiness checks because its local payment encryption HSM session is disconnected. "
            "However, Service 'checkout-gateway-svc' has 'publishNotReadyAddresses: true' set in its spec, "
            "forcing Kubernetes EndpointSlices to keep advertising the unready pod IP (10.244.4.91) as an "
            "active backend and routing live customer checkout traffic to the broken pod."
        ),
        "injected_fault": "Service 'checkout-gateway-svc' configured with spec.publishNotReadyAddresses: true, causing EndpointSlices and kube-proxy to route live traffic to unready pod 'checkout-gateway-4e5f6a7b8-r9m1c'.",
        "expected_root_cause_category": "NETWORK_DNS_FAILURE",
        "expected_subtype": "SERVICE_ROUTES_UNHEALTHY_PODS",
        "expected_severity": "HIGH",
        "expected_impacted_resources": ["checkout-gateway-4e5f6a7b8-r9m1c"],
        "expected_namespace": "payments",
        "expected_container": "checkout-proxy",
        "expected_node": "node-general-06",
        "ground_truth_rca": (
            "Service 'checkout-gateway-svc' in namespace 'payments' is routing live traffic to unhealthy/unready "
            "pod 'checkout-gateway-4e5f6a7b8-r9m1c' (10.244.4.91) because 'publishNotReadyAddresses: true' "
            "is enabled on the Service, bypassing readiness gating and causing HTTP 502/503 checkout failures."
        ),
        "ground_truth_evidence_keywords": [
            "publishNotReadyAddresses: true",
            "routing live traffic to unready pod",
            "unready endpoint",
        ],
        "expected_remediation_commands": [
            "kubectl patch svc <service-name> -p '{\"spec\":{\"publishNotReadyAddresses\":false}}'",
            "kubectl get endpointslice -o wide && kubectl describe pod checkout-gateway-4e5f6a7b8-r9m1c",
        ],
        "log_content": """2026-10-14T17:25:01.140Z WARN pod=checkout-gateway-4e5f6a7b8-r9m1c namespace=payments container=checkout-proxy node=node-general-06 HSM session state=DISCONNECTED; health endpoint /readyz returning HTTP 503 Not Ready (pod status: 0/1 Ready)
2026-10-14T17:25:04.220Z WARN pod=checkout-gateway-4e5f6a7b8-r9m1c namespace=payments container=checkout-proxy node=node-general-06 endpointslice-controller: Service payments/checkout-gateway-svc has publishNotReadyAddresses: true enabled; including unready endpoint 10.244.4.91 (pod checkout-gateway-4e5f6a7b8-r9m1c) in active EndpointSlice
2026-10-14T17:25:08.510Z ERROR pod=checkout-gateway-4e5f6a7b8-r9m1c namespace=payments container=checkout-proxy node=node-general-06 Service checkout-gateway-svc routing live traffic to unready pod checkout-gateway-4e5f6a7b8-r9m1c (10.244.4.91:8443) despite Readiness=False
2026-10-14T17:25:09.105Z ERROR pod=checkout-gateway-4e5f6a7b8-r9m1c namespace=payments container=checkout-proxy node=node-general-06 POST /api/v1/checkout/authorize HTTP/1.1 502 Bad Gateway: request routed to unready endpoint 10.244.4.91 while HSM session is uninitialized
2026-10-14T17:25:12.640Z ERROR pod=checkout-gateway-4e5f6a7b8-r9m1c namespace=payments container=checkout-proxy node=node-general-06 ingress-gateway: upstream payments/checkout-gateway-svc routed 38 client requests to unhealthy pod checkout-gateway-4e5f6a7b8-r9m1c (HTTP 502/503 error rate: 100%)
""",
    },
]


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_cases = []

    for tc in TEST_CASES:
        log_path = BASE_DIR / tc["log_file"]
        log_path.write_text(tc["log_content"].strip() + "\n", encoding="utf-8")
        manifest_entry = {k: v for k, v in tc.items() if k != "log_content"}
        manifest_cases.append(manifest_entry)

    manifest = {
        "dataset_name": "K8s-Investigation-Agent Incident Evaluation Benchmark",
        "version": "1.0.0",
        "total_cases": len(manifest_cases),
        "cases": manifest_cases,
    }
    manifest_path = BASE_DIR / "eval_cases.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(manifest_cases)} log files in {LOGS_DIR} and manifest at {manifest_path}")


if __name__ == "__main__":
    main()
