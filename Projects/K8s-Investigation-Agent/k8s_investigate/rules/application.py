"""
Diagnostic rule for Application Panics, Unhandled Runtime Exceptions, and Fatal Crashes.
Detects Python tracebacks, Go runtime panics, Java unhandled exceptions, and Node.js uncaught exceptions.
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


APP_CRASH_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r"panic:\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"Exception in thread\s+['\"]?([^'\"]+)['\"]?\s+([a-zA-Z0-9_\.]+Exception|Error):\s*([^\n]+)?", re.IGNORECASE),
    re.compile(r"Uncaught TypeError:\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"FATAL EXCEPTION:\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"fatal error:\s*([^\n]+)", re.IGNORECASE),
]


class ApplicationPanicRule(DiagnosticRule):
    rule_id = "RULE_APPLICATION_PANIC_EXCEPTION"
    category = FailureCategory.APPLICATION_PANIC
    title = "Application Fatal Exception or Runtime Panic"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        exception_types = []
        reasons = []

        for entry in entries:
            # Check if entry is marked as stack trace or contains crash pattern
            text = f"{entry.message} {entry.raw}"
            for pattern in APP_CRASH_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {"matched_pattern": pattern.pattern}

                    if "traceback" in matched_str.lower():
                        exception_types.append("Python Traceback")
                    elif "panic:" in matched_str.lower():
                        exception_types.append("Go Runtime Panic")
                    elif "exception in thread" in matched_str.lower():
                        exception_types.append("Java Thread Exception")
                    elif "typeerror" in matched_str.lower():
                        exception_types.append("Node.js Uncaught Exception")

                    reason = f"Application crashed with stack trace / panic: '{matched_str[:80]}'"
                    snippet = self.extract_evidence_snippet(
                        entry, entries, reason=reason, params=params, context_before=1, context_after=3
                    )
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        types_str = ", ".join(sorted(set(exception_types))) if exception_types else "Runtime Crash"

        description = (
            f"The application process raised an unhandled exception or panic [{types_str}]. "
            f"The error caused the main process thread to crash, terminating the container."
        )

        remediations = [
            "Inspect the logged stack trace to identify the faulty file and line number.",
            "Verify application environment variables and configuration files mounted into the pod.",
            "Ensure proper error handling (try-catch / recovery handlers) around external dependencies or unvalidated inputs.",
        ]

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=f"Application Crash: {types_str}",
            severity=Severity.HIGH,
            description=description,
            confidence=0.90,
            primary_indicator=reasons[0][:100] if reasons else "Application Crash",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
