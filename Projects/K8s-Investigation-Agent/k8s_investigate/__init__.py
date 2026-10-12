"""
Kubernetes Investigation Agent.
Automated log investigation, causal root cause analysis, evidence extraction, and remediation.
"""

from k8s_investigate.agent import KubernetesInvestigationAgent
from k8s_investigate.engine import InvestigationEngine
from k8s_investigate.models import (
    BlastRadius,
    EvidenceSnippet,
    FailureCategory,
    Finding,
    InvestigationReport,
    LogEntry,
    RemediationAction,
    RootCause,
    Severity,
    TimelineEvent,
)
from k8s_investigate.parser import LogParser
from k8s_investigate.reporter import ReportRenderer

__version__ = "1.0.0"

__all__ = [
    "KubernetesInvestigationAgent",
    "InvestigationEngine",
    "LogParser",
    "ReportRenderer",
    "InvestigationReport",
    "RootCause",
    "Finding",
    "EvidenceSnippet",
    "TimelineEvent",
    "RemediationAction",
    "BlastRadius",
    "FailureCategory",
    "Severity",
    "LogEntry",
]
