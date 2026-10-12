"""
Base classes for Kubernetes Diagnostic Rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from k8s_investigate.models import (
    EvidenceSnippet,
    FailureCategory,
    Finding,
    LogEntry,
    Severity,
)


class DiagnosticRule(ABC):
    """Abstract base class for all failure detection rules."""

    rule_id: str
    category: FailureCategory
    title: str
    default_severity: Severity

    @abstractmethod
    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        """
        Analyzes the log entries and returns a Finding if the pattern/failure is detected,
        or None if no failure of this type is found.
        """
        pass

    def extract_evidence_snippet(
        self,
        entry: LogEntry,
        entries: List[LogEntry],
        reason: str,
        params: Optional[Dict[str, Any]] = None,
        context_before: int = 1,
        context_after: int = 1,
    ) -> EvidenceSnippet:
        """
        Extracts a supporting evidence snippet surrounding the given entry,
        showing exact log lines for debugging.
        """
        idx = entries.index(entry) if entry in entries else -1
        if idx == -1:
            raw_lines = [f"[L{entry.line_number}] {entry.raw}"]
            return EvidenceSnippet(
                start_line=entry.line_number,
                end_line=entry.line_number,
                raw_lines=raw_lines,
                timestamp=entry.timestamp,
                highlighted_reason=reason,
                extracted_params=params or {},
            )

        start_idx = max(0, idx - context_before)
        end_idx = min(len(entries), idx + context_after + 1)
        sub_entries = entries[start_idx:end_idx]

        raw_lines = [f"[L{e.line_number}] {e.raw}" for e in sub_entries]
        return EvidenceSnippet(
            start_line=sub_entries[0].line_number,
            end_line=sub_entries[-1].line_number,
            raw_lines=raw_lines,
            timestamp=entry.timestamp,
            highlighted_reason=reason,
            extracted_params=params or {},
        )
