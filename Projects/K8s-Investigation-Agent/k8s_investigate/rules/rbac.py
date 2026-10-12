"""
Diagnostic rule for Kubernetes RBAC (Role-Based Access Control) and Admission Webhook failures.
Detects 403 Forbidden errors, missing ServiceAccounts, and unauthorized API requests.
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


RBAC_PATTERNS = [
    re.compile(r"is forbidden:\s*User\s+['\"]?([^'\"]+)['\"]?\s+cannot\s+([a-z]+)\s+resource\s+['\"]?([^'\"]+)['\"]?(?:\s+in API group\s+['\"]?([^'\"]*)['\"])?", re.IGNORECASE),
    re.compile(r"cannot\s+([a-z]+)\s+resource\s+['\"]?([^'\"]+)['\"]?\s+in API group\s+['\"]?([^'\"]*)['\"]?", re.IGNORECASE),
    re.compile(r"User\s+['\"]?(system:serviceaccount:[^'\"]+)['\"]?\s+cannot", re.IGNORECASE),
    re.compile(r"serviceaccount\s+['\"]?([^'\"]+)['\"]?\s+not found", re.IGNORECASE),
    re.compile(r"failed to call webhook\s+['\"]?([^'\"]+)['\"]?:\s*(.+)", re.IGNORECASE),
    re.compile(r"HTTP 403 Forbidden", re.IGNORECASE),
]


class RBACRule(DiagnosticRule):
    rule_id = "RULE_K8S_RBAC_FAILURE"
    category = FailureCategory.RBAC_AUTH_FAILURE
    title = "Kubernetes RBAC Authorization / Permission Denied (403 Forbidden)"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        service_accounts = set()
        missing_permissions = []
        reasons = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in RBAC_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    sa_match = re.search(r"system:serviceaccount:([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]+)", matched_str)
                    if sa_match:
                        sa_ns, sa_name = sa_match.group(1), sa_match.group(2)
                        service_accounts.add(f"{sa_ns}/{sa_name}")
                        params["service_account"] = sa_name
                        params["namespace"] = sa_ns

                    verb_match = re.search(r"cannot\s+([a-z]+)\s+resource\s+['\"]?([^'\"]+)['\"]?", matched_str, re.IGNORECASE)
                    if verb_match:
                        verb, res = verb_match.group(1), verb_match.group(2)
                        missing_permissions.append(f"{verb} {res}")
                        params["verb"] = verb
                        params["resource"] = res

                    reason = f"RBAC authorization failure: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        sa_info = f" ServiceAccount(s): {', '.join(sorted(service_accounts))}." if service_accounts else ""
        perm_info = f" Denied operations: {', '.join(sorted(set(missing_permissions)))}." if missing_permissions else ""

        description = (
            f"The application or controller was denied permission by the Kubernetes API server (403 Forbidden).{sa_info}{perm_info} "
            f"The pod's ServiceAccount lacks the required Role/ClusterRole bindings."
        )

        remediations = [
            "Check the pod's configured ServiceAccount: `kubectl get pod <pod-name> -o jsonpath='{.spec.serviceAccountName}'`.",
            "Verify existing permissions with `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<namespace>:<serviceaccount>`.",
            "Create or update a Role / ClusterRole and corresponding RoleBinding to grant the required API permissions.",
        ]

        return Finding(
            id=self.rule_id,
            category=self.category,
            title="Kubernetes RBAC Permission Denied (403 Forbidden)",
            severity=Severity.HIGH,
            description=description,
            confidence=0.98,
            primary_indicator=reasons[0] if reasons else "RBAC 403 Forbidden",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
