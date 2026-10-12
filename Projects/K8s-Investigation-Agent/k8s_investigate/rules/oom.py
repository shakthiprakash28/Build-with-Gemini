"""
Diagnostic rule for Out Of Memory (OOM) kills and memory exhaustion.
Detects container OOMKilled events, Linux cgroup OOM termination (exit code 137),
JVM heap exhaustion, Go runtime memory limits, and Node.js heap exhaustion.
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


OOM_PATTERNS = [
    re.compile(r"\bOOMKilled\b", re.IGNORECASE),
    re.compile(r"\bexit code\s*[:=]?\s*137\b", re.IGNORECASE),
    re.compile(r"\bterminated with exit code 137\b", re.IGNORECASE),
    re.compile(r"cgroup out of memory:\s*Killed process\s*(\d+)\s*\(([^)]+)\)", re.IGNORECASE),
    re.compile(r"invoked oom-killer:\s*gfp_mask=", re.IGNORECASE),
    re.compile(r"java\.lang\.OutOfMemoryError(?::\s*([^\n]+))?", re.IGNORECASE),
    re.compile(r"fatal error:\s*runtime:\s*out of memory", re.IGNORECASE),
    re.compile(r"JavaScript heap out of memory", re.IGNORECASE),
    re.compile(r"Memory cgroup out of memory: Kill process (\d+) \(([^)]+)\) score (\d+)", re.IGNORECASE),
    re.compile(r"Pod memory limit exceeded:\s*([0-9\.]+\s*(?:Mi|Gi|Ki|MB|GB))?", re.IGNORECASE),
    re.compile(r"task killed by OOM killer", re.IGNORECASE),
]


class OOMKillRule(DiagnosticRule):
    rule_id = "RULE_K8S_OOM_KILL"
    category = FailureCategory.OOM_KILL
    title = "Container Terminated Due To Out-Of-Memory (OOMKilled / Exit 137)"
    default_severity = Severity.CRITICAL

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        details_list = []
        extracted_limits = set()

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in OOM_PATTERNS:
                match = pattern.search(text)
                if match:
                    reason = f"Detected OOM memory exhaustion: '{match.group(0)}'"
                    params: Dict[str, Any] = {"pattern_matched": pattern.pattern}
                    
                    if "java.lang.OutOfMemoryError" in match.group(0):
                        params["type"] = "JVM_HEAP_EXHAUSTION"
                    elif "exit code 137" in match.group(0).lower():
                        params["type"] = "SIGKILL_CGROUP_OOM"
                    elif "JavaScript heap" in match.group(0):
                        params["type"] = "NODEJS_HEAP_EXHAUSTION"

                    # Check for memory limits in the text
                    limit_match = re.search(r"limit(?: exceeded)?:\s*([0-9\.]+\s*(?:Mi|Gi|Ki|MB|GB))", text, re.IGNORECASE) or \
                                  re.search(r"\b([0-9\.]+\s*(?:Mi|Gi|Ki|MB|GB))\s+limit\b", text, re.IGNORECASE)
                    if limit_match:
                        lim_str = limit_match.group(1).strip()
                        extracted_limits.add(lim_str)
                        params["limit"] = lim_str
                    elif match.lastindex:
                        for g_idx in range(1, match.lastindex + 1):
                            val = match.group(g_idx)
                            if val and any(u in val for u in ["Mi", "Gi", "MB", "GB"]):
                                extracted_limits.add(val.strip())
                                params["limit"] = val.strip()

                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)
                    
                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    details_list.append(match.group(0))
                    break

        if not evidence_snippets:
            return None

        # Build comprehensive remediation recommendations
        remediations = [
            "Inspect the memory limit specified in the container specification (spec.containers[*].resources.limits.memory).",
            "Increase container memory limit: `kubectl set resources deployment/<name> --limits=memory=1Gi --requests=memory=512Mi`.",
            "Review application memory utilization and profile for memory leaks (e.g., unbounded caches, leaked DB connections, large in-memory batch processing).",
        ]

        if any("java.lang.OutOfMemoryError" in d for d in details_list):
            remediations.append(
                "Tune JVM heap parameters (-XX:MaxRAMPercentage=75.0 or -Xmx) to prevent JVM heap from exceeding container cgroup memory limits."
            )
        if any("JavaScript heap" in d for d in details_list):
            remediations.append(
                "Increase Node.js max old space size via environment variable: `NODE_OPTIONS=\"--max-old-space-size=4096\"`."
            )

        limit_info = f" (Observed limit: {', '.join(extracted_limits)})" if extracted_limits else ""
        description = (
            f"The container or process was terminated because its memory consumption exceeded the allocated "
            f"cgroup memory limit or physical host memory{limit_info}. The Linux kernel OOM killer or Kubernetes "
            f"kubelet dispatched SIGKILL (signal 9, exit code 137) to protect the node from exhaustion."
        )

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=self.title,
            severity=self.default_severity,
            description=description,
            confidence=0.98,
            primary_indicator=details_list[0] if details_list else "OOMKilled",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
