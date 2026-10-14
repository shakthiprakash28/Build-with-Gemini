"""
Diagnostic rule for Pod Scheduling failures, Resource Starvation, and Node Health.
Detects FailedScheduling, Insufficient CPU/Memory, Node Taints, and NodeNotReady states.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from k8s_investigate.models import (
    EvidenceSnippet,
    FailureCategory,
    Finding,
    LogEntry,
    Severity,
)
from k8s_investigate.rules.base import DiagnosticRule


SCHEDULING_PATTERNS = [
    re.compile(r"\bFailedScheduling\b:\s*(.+)", re.IGNORECASE),
    re.compile(r"0/\d+\s+nodes are available:\s*(.+)", re.IGNORECASE),
    re.compile(r"Insufficient\s+(cpu|memory|ephemeral-storage)", re.IGNORECASE),
    re.compile(r"node\(s\) had untolerated taint\s*\{([^}]+)\}", re.IGNORECASE),
    re.compile(r"didn't match PodTopologySpread", re.IGNORECASE),
    re.compile(r"node\(s\) had volume node-affinity conflict", re.IGNORECASE),
    re.compile(r"Node\s+([a-zA-Z0-9_\-\.]+)\s+status is now:\s*NodeNotReady", re.IGNORECASE),
    re.compile(r"PLEG is not healthy:\s*(.+)", re.IGNORECASE),
    re.compile(r"\bKubeletNotReady\b:\s*(.+)", re.IGNORECASE),
    re.compile(r"NodeCondition.*DiskPressure.*True", re.IGNORECASE),
    re.compile(r"NodeCondition.*MemoryPressure.*True", re.IGNORECASE),
    re.compile(r"The node was low on resource:\s*(memory|ephemeral-storage)", re.IGNORECASE),
    re.compile(r"System OOM encountered,\s*victim process:\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"CPU throttling detected:\s*(.+)", re.IGNORECASE),
    re.compile(r"nr_throttled=\d+.*throttled_time=\d+", re.IGNORECASE),
    re.compile(r"CFS quota exceeded.*throttled", re.IGNORECASE),
]


class SchedulingRule(DiagnosticRule):
    rule_id = "RULE_K8S_SCHEDULING_FAILURE"
    category = FailureCategory.SCHEDULING_NODE_FAILURE
    title = "Pod Scheduling Failure / Node Resource Pressure / CPU Throttling"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        bottlenecks = set()
        reasons = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in SCHEDULING_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}
                    low_str = matched_str.lower()

                    if "throttl" in low_str or "cfs quota" in low_str:
                        bottlenecks.add("CPU_THROTTLING")
                        params["subtype"] = "CPU_THROTTLING"
                        params["resource"] = "CPU"
                    elif "memorypressure" in low_str or "low on resource: memory" in low_str or "system oom" in low_str:
                        bottlenecks.add("NODE_MEMORY_PRESSURE")
                        params["subtype"] = "NODE_MEMORY_PRESSURE"
                        params["resource"] = "NODE_MEMORY"
                    elif "nodenotready" in low_str or "pleg is not healthy" in low_str or "kubeletnotready" in low_str:
                        bottlenecks.add("NODE_NOT_READY")
                        params["subtype"] = "NODE_NOT_READY"
                        params["issue"] = "NODE_OFFLINE"
                    else:
                        if "cpu" in low_str:
                            bottlenecks.add("INSUFFICIENT_CPU")
                            params["resource"] = "CPU"
                        if "memory" in low_str:
                            bottlenecks.add("INSUFFICIENT_MEMORY")
                            params["resource"] = "MEMORY"
                        if "taint" in low_str:
                            bottlenecks.add("UNRESOLVED_TAINT")
                            params["issue"] = "TAINT"

                    reason = f"Resource/Node constraint detected: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        bottlenecks_str = ", ".join(sorted(bottlenecks)) if bottlenecks else "Cluster Capacity Constraints"
        if "CPU_THROTTLING" in bottlenecks:
            title = "Container CFS CPU Quota Throttling Detected"
            description = (
                f"Container CPU usage is being aggressively throttled by the Linux kernel CFS bandwidth controller [{bottlenecks_str}]. "
                f"Overly restrictive `resources.limits.cpu` causes worker threads to stall waiting for the next 100ms quota period, "
                f"leading to severe tail-latency spikes without terminating the container."
            )
        elif "NODE_MEMORY_PRESSURE" in bottlenecks:
            title = "Node MemoryPressure & Kubelet Pod Eviction Detected"
            description = (
                f"Worker node experienced critical MemoryPressure and crossed kubelet eviction thresholds [{bottlenecks_str}]. "
                f"Kubelet reclaimed node memory by forcefully evicting pods ordered by QoS class (BestEffort and Burstable exceeding requests)."
            )
        elif "NODE_NOT_READY" in bottlenecks:
            title = "Worker Node NotReady / Kubelet PLEG Unhealthy"
            description = (
                f"Worker node transitioned to NodeNotReady state [{bottlenecks_str}]. "
                f"Kubelet Pod Lifecycle Event Generator (PLEG) or container runtime failed health checks, causing pod disruption and eviction."
            )
        else:
            title = "FailedScheduling / Resource Request & Limit Starvation Detected"
            description = (
                f"Kubernetes default-scheduler cannot place the pod on any worker node [{bottlenecks_str}]. "
                f"The pod remains in 'Pending' state because requested CPU/memory exceeds allocatable node capacity."
            )

        remediations = [
            "Inspect cluster node capacities and allocatable resources: `kubectl describe nodes | grep -A 8 'Allocated resources'`.",
            "Verify pod resource requests and limits (`spec.containers[*].resources`) to ensure they match workload needs and node sizing.",
        ]
        if "CPU_THROTTLING" in bottlenecks:
            remediations.extend([
                "Increase or remove hard CPU limits (`resources.limits.cpu`) while keeping accurate `resources.requests.cpu`: `kubectl set resources deployment/<name> --limits=cpu=1000m --requests=cpu=500m`.",
                "Inspect container cgroup throttling metrics (`container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total`).",
            ])
        if "NODE_MEMORY_PRESSURE" in bottlenecks:
            remediations.extend([
                "Inspect node memory conditions and eviction events: `kubectl describe node <node-name>`.",
                "Set accurate memory requests equal to limits (Guaranteed QoS) for critical workloads to protect them from node eviction.",
            ])
        if "INSUFFICIENT_CPU" in bottlenecks or "INSUFFICIENT_MEMORY" in bottlenecks:
            remediations.extend([
                "Lower excessive pod `resources.requests` to fit within worker node allocatable capacity, or scale out the node pool.",
                "Review namespace ResourceQuota and LimitRange constraints: `kubectl describe quota,limitrange -n <namespace>`.",
            ])
        if "UNRESOLVED_TAINT" in bottlenecks:
            remediations.append("Check node taints (`kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints`) and add matching tolerations to pod spec.")
        if "NODE_NOT_READY" in bottlenecks:
            remediations.append("Investigate unhealthy node and container runtime: `kubectl describe node <node-name>` and `journalctl -u kubelet -u containerd -n 100`.")

        if "CPU_THROTTLING" in bottlenecks:
            primary_subtype = "CPU_THROTTLING"
        elif "NODE_MEMORY_PRESSURE" in bottlenecks:
            primary_subtype = "NODE_MEMORY_PRESSURE"
        elif "NODE_NOT_READY" in bottlenecks:
            primary_subtype = "NODE_NOT_READY"
        elif "INSUFFICIENT_CPU" in bottlenecks:
            primary_subtype = "INSUFFICIENT_CPU"
        elif "INSUFFICIENT_MEMORY" in bottlenecks:
            primary_subtype = "INSUFFICIENT_MEMORY"
        else:
            primary_subtype = sorted(list(bottlenecks))[0] if bottlenecks else "GENERIC"

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=title,
            severity=Severity.CRITICAL if "NODE_NOT_READY" in bottlenecks or "NODE_MEMORY_PRESSURE" in bottlenecks else Severity.HIGH,
            description=description,
            confidence=0.97,
            primary_indicator=reasons[0] if reasons else "FailedScheduling",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
            metadata={"subtype": primary_subtype, "bottlenecks": sorted(list(bottlenecks))},
        )
