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
    re.compile(r"NodeCondition.*DiskPressure.*True", re.IGNORECASE),
    re.compile(r"NodeCondition.*MemoryPressure.*True", re.IGNORECASE),
]


class SchedulingRule(DiagnosticRule):
    rule_id = "RULE_K8S_SCHEDULING_FAILURE"
    category = FailureCategory.SCHEDULING_NODE_FAILURE
    title = "Pod Scheduling Failure / Cluster Resource Starvation (FailedScheduling)"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        bottlenecks = set()
        taints = set()
        reasons = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in SCHEDULING_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    if "cpu" in matched_str.lower():
                        bottlenecks.add("INSUFFICIENT_CPU")
                        params["resource"] = "CPU"
                    if "memory" in matched_str.lower():
                        bottlenecks.add("INSUFFICIENT_MEMORY")
                        params["resource"] = "MEMORY"
                    if "taint" in matched_str.lower():
                        bottlenecks.add("UNRESOLVED_TAINT")
                        params["issue"] = "TAINT"
                    if "nodenotready" in matched_str.lower():
                        bottlenecks.add("NODE_NOT_READY")
                        params["issue"] = "NODE_OFFLINE"

                    reason = f"Scheduling constraint violated: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        bottlenecks_str = ", ".join(sorted(bottlenecks)) if bottlenecks else "Cluster Capacity Constraints"
        description = (
            f"Kubernetes default-scheduler cannot place the pod on any worker node [{bottlenecks_str}]. "
            f"The pod remains in 'Pending' state and cannot be allocated execution slots."
        )

        remediations = [
            "Inspect cluster node capacities and allocatable resources: `kubectl describe nodes | grep -A 8 'Allocated resources'`.",
            "Verify pod resource requests (`spec.containers[*].resources.requests`) - ensure requests are realistic and not over-committed.",
        ]
        if "INSUFFICIENT_CPU" in bottlenecks or "INSUFFICIENT_MEMORY" in bottlenecks:
            remediations.extend([
                "Trigger node pool scale-out or configure Cluster Autoscaler / Karpenter to provision additional worker nodes.",
                "Review lower-priority workloads that could be evicted or downscaled.",
            ])
        if "UNRESOLVED_TAINT" in bottlenecks:
            remediations.append("Check node taints (`kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints`) and add matching tolerations to pod spec.")
        if "NODE_NOT_READY" in bottlenecks:
            remediations.append("Investigate unhealthy nodes: `kubectl describe node <node-name>` and check Kubelet systemd logs (`journalctl -u kubelet -n 100`).")

        return Finding(
            id=self.rule_id,
            category=self.category,
            title="FailedScheduling / Resource Starvation Detected",
            severity=Severity.HIGH,
            description=description,
            confidence=0.97,
            primary_indicator=reasons[0] if reasons else "FailedScheduling",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
