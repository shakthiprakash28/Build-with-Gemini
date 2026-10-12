"""
Diagnostic rule for Kubernetes Health Check (Liveness, Readiness, Startup) Probe Failures.
Detects probe timeouts, HTTP 5xx failures, connection refused during probing,
and container restarts induced by liveness probe enforcement.
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


PROBE_PATTERNS = [
    re.compile(r"Liveness probe failed:\s*(.+)", re.IGNORECASE),
    re.compile(r"Readiness probe failed:\s*(.+)", re.IGNORECASE),
    re.compile(r"Startup probe failed:\s*(.+)", re.IGNORECASE),
    re.compile(r"Container failed liveness probe(?:\.\s*Container will be killed and recreated)?", re.IGNORECASE),
    re.compile(r"HTTP probe failed with statuscode:\s*([0-9]{3})", re.IGNORECASE),
    re.compile(r"probe failed:\s*Get\s+['\"]?https?://[^:\s]+(?::\d+)?([^'\"]*)['\"]?:\s*(.+)", re.IGNORECASE),
    re.compile(r"probe err:\s*(.+)", re.IGNORECASE),
]


class ProbeFailureRule(DiagnosticRule):
    rule_id = "RULE_K8S_PROBE_FAILURE"
    category = FailureCategory.PROBE_FAILURE
    title = "Kubernetes Health Check (Liveness/Readiness/Startup) Probe Failed"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        failed_types = set()
        status_codes = set()
        reasons = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in PROBE_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    # Determine probe type
                    if "liveness" in matched_str.lower():
                        failed_types.add("Liveness")
                        params["probe_type"] = "Liveness"
                    elif "readiness" in matched_str.lower():
                        failed_types.add("Readiness")
                        params["probe_type"] = "Readiness"
                    elif "startup" in matched_str.lower():
                        failed_types.add("Startup")
                        params["probe_type"] = "Startup"

                    # HTTP code
                    code_m = re.search(r"statuscode:\s*([0-9]{3})", matched_str, re.IGNORECASE) or \
                             re.search(r"HTTP\s+([0-9]{3})", matched_str, re.IGNORECASE)
                    if code_m:
                        code = code_m.group(1)
                        status_codes.add(code)
                        params["http_status"] = code

                    # Timeout / Connection issue
                    if "deadline exceeded" in matched_str.lower() or "timeout" in matched_str.lower():
                        params["failure_mode"] = "TIMEOUT"
                    elif "connection refused" in matched_str.lower():
                        params["failure_mode"] = "CONNECTION_REFUSED"

                    reason = f"Health check probe failed: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        has_liveness = "Liveness" in failed_types
        severity = Severity.CRITICAL if has_liveness else Severity.HIGH

        types_str = "/".join(sorted(failed_types)) if failed_types else "Health"
        codes_str = f" (HTTP status: {', '.join(sorted(status_codes))})" if status_codes else ""

        description = (
            f"Kubernetes {types_str} probe failed{codes_str}. "
            f"{'Failing liveness probes force kubelet to kill and restart the container, potentially causing restart loops. ' if has_liveness else ''}"
            f"Failing readiness probes cause the pod endpoint to be removed from Service load balancing, preventing traffic ingress."
        )

        remediations = [
            "Verify whether the application process is overwhelmed or deadlocked during probe execution.",
            "Inspect probe configuration in pod spec (`initialDelaySeconds`, `periodSeconds`, `timeoutSeconds`, `failureThreshold`).",
            "Increase `timeoutSeconds` if the application takes longer to respond under load (e.g. from 1s to 5s).",
            "If initialization takes significant time (e.g. heavy DB migrations or cache warming), implement a `startupProbe` to shield the `livenessProbe`.",
            "Verify healthcheck handler logic: ensure health checks don't make blocking synchronous calls to unready downstream dependencies.",
        ]

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=f"{types_str} Probe Failure Detected",
            severity=severity,
            description=description,
            confidence=0.95,
            primary_indicator=reasons[0] if reasons else f"{types_str} Probe Failure",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
