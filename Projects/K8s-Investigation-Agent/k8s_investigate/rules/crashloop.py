"""
Diagnostic rule for CrashLoopBackOff and continuous container restart cycles.
Detects CrashLoopBackOff events, process termination exit codes (1, 2, 134, 139, 143),
and recurring startup failures.
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


CRASH_PATTERNS = [
    re.compile(r"\bCrashLoopBackOff\b", re.IGNORECASE),
    re.compile(r"Back-off restarting failed container\s*['\"]?([a-zA-Z0-9_\-\.]+)?['\"]?", re.IGNORECASE),
    re.compile(r"restarting failed container\s+([a-zA-Z0-9_\-\.]+)\s+in pod\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"\bterminated with exit code\s*([0-9]+)\b", re.IGNORECASE),
    re.compile(r"\bexit code\s*[:=]?\s*([0-9]+)\b", re.IGNORECASE),
    re.compile(r"Container\s+([a-zA-Z0-9_\-\.]+)\s+failed to start", re.IGNORECASE),
    re.compile(r"Segmentation fault(?:\s+\(core dumped\))?", re.IGNORECASE),
    re.compile(r"SIGSEGV:\s*segmentation violation", re.IGNORECASE),
    re.compile(r"SIGABRT:\s*abort", re.IGNORECASE),
]


EXIT_CODE_MEANINGS = {
    "1": "General application error or unhandled runtime exception.",
    "2": "Misuse of shell built-ins or command syntax error.",
    "126": "Command invoked cannot execute (permission problem or not executable).",
    "127": "Command not found inside container filesystem (check PATH or entrypoint binary).",
    "128": "Invalid argument to exit.",
    "134": "SIGABRT - Process aborted by system or assertion failure.",
    "137": "SIGKILL - Terminated by external signal (commonly Out Of Memory / cgroup limit).",
    "139": "SIGSEGV - Segmentation fault (memory access violation in binary/native library).",
    "143": "SIGTERM - Graceful termination requested by kubelet (preStop or timeout exceeded).",
}


class CrashLoopRule(DiagnosticRule):
    rule_id = "RULE_K8S_CRASHLOOP_BACKOFF"
    category = FailureCategory.CRASH_LOOP
    title = "Pod In CrashLoopBackOff / Repeated Process Failure"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        detected_codes = set()
        detected_containers = set()
        is_explicit_backoff = False

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in CRASH_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    if "crashloopbackoff" in matched_str.lower() or "restarting failed container" in matched_str.lower():
                        is_explicit_backoff = True

                    params: Dict[str, Any] = {}
                    # Check exit codes
                    code_match = re.search(r"exit code\s*[:=]?\s*([0-9]+)", matched_str, re.IGNORECASE) or \
                                 re.search(r"terminated with exit code\s*([0-9]+)", matched_str, re.IGNORECASE)
                    if code_match:
                        code = code_match.group(1)
                        if code != "0":  # 0 is clean exit
                            detected_codes.add(code)
                            params["exit_code"] = code
                            params["exit_meaning"] = EXIT_CODE_MEANINGS.get(code, "Non-zero exit code")

                    # Check container name
                    if match.groups():
                        for g in match.groups():
                            if g and not g.isdigit() and len(g) > 2:
                                detected_containers.add(g)
                                params["container"] = g

                    reason = f"Container failure / CrashLoop indicator: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    break

        if not evidence_snippets:
            return None

        # Severity is CRITICAL if explicit CrashLoopBackOff is active, HIGH otherwise
        severity = Severity.CRITICAL if is_explicit_backoff else Severity.HIGH

        code_explanations = []
        for code in sorted(detected_codes):
            explanation = EXIT_CODE_MEANINGS.get(code, "Unknown non-zero exit code")
            code_explanations.append(f"Exit Code {code}: {explanation}")

        codes_summary = f" (Identified exit codes: {', '.join(sorted(detected_codes))})" if detected_codes else ""
        containers_summary = f" Container(s): {', '.join(sorted(detected_containers))}." if detected_containers else ""

        description = (
            f"The container is repeatedly failing and entering CrashLoopBackOff{codes_summary}.{containers_summary} "
            f"Kubernetes applies an exponential back-off delay (10s, 20s, 40s ... up to 5m) before attempting to restart the container."
        )

        remediations = [
            "Fetch previous terminated container logs: `kubectl logs <pod-name> --previous` or `kubectl logs <pod-name> -c <container> -p`.",
            "Describe the pod to review the termination state, last exit code, and message: `kubectl describe pod <pod-name>`.",
            "Verify container entrypoint and command syntax in deployment specification.",
            "Run an interactive debug shell in a clone container: `kubectl debug <pod-name> -it --image=busybox`.",
        ]
        if "127" in detected_codes:
            remediations.append("Exit code 127 indicates missing binary. Verify that the Dockerfile CMD / ENTRYPOINT path exists and has execute (+x) permissions.")
        if "139" in detected_codes:
            remediations.append("Exit code 139 indicates SIGSEGV (segmentation fault). Check native libraries (C/C++ bindings, OpenSSL, glibc/musl compatibility in alpine).")

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=self.title,
            severity=severity,
            description=description,
            confidence=0.95 if is_explicit_backoff else 0.85,
            primary_indicator=f"CrashLoopBackOff{codes_summary}",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
