"""
Data models for Kubernetes Investigation Agent.
Defines structured schemas for log entries, detected evidence, timeline events,
root cause analysis, actionable remediations, and full investigation reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        ranks = {
            Severity.CRITICAL: 5,
            Severity.HIGH: 4,
            Severity.MEDIUM: 3,
            Severity.LOW: 2,
            Severity.INFO: 1,
        }
        return ranks.get(self, 0)

    def __ge__(self, other: Severity) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank

    def __gt__(self, other: Severity) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __le__(self, other: Severity) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __lt__(self, other: Severity) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank


class FailureCategory(str, Enum):
    OOM_KILL = "OOM_KILL"
    CRASH_LOOP = "CRASH_LOOP"
    IMAGE_PULL_FAILURE = "IMAGE_PULL_FAILURE"
    PROBE_FAILURE = "PROBE_FAILURE"
    NETWORK_DNS_FAILURE = "NETWORK_DNS_FAILURE"
    STORAGE_PVC_FAILURE = "STORAGE_PVC_FAILURE"
    SCHEDULING_NODE_FAILURE = "SCHEDULING_NODE_FAILURE"
    RBAC_AUTH_FAILURE = "RBAC_AUTH_FAILURE"
    CONFIG_SECRET_FAILURE = "CONFIG_SECRET_FAILURE"
    APPLICATION_PANIC = "APPLICATION_PANIC"
    UNKNOWN = "UNKNOWN"


class LogEntry(BaseModel):
    """Represents a normalized log line or structured event."""
    line_number: int
    raw: str
    timestamp: Optional[datetime] = None
    level: str = "INFO"
    stream: Optional[str] = None  # stdout, stderr, etc.
    pod: Optional[str] = None
    namespace: Optional[str] = None
    container: Optional[str] = None
    node: Optional[str] = None
    component: Optional[str] = None  # kubelet, coredns, app, ingress, etc.
    message: str = ""
    is_stack_trace: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceSnippet(BaseModel):
    """Exact log evidence supporting a finding."""
    start_line: int
    end_line: int
    raw_lines: List[str]
    timestamp: Optional[datetime] = None
    highlighted_reason: str
    extracted_params: Dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """An individual problem detected by an investigation rule."""
    id: str
    category: FailureCategory
    title: str
    severity: Severity
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    primary_indicator: str
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    impacted_resources: List[str] = Field(default_factory=list)
    suggested_remediation: List[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """Chronologically ordered event during the incident."""
    timestamp: Optional[datetime] = None
    relative_time_str: str = ""
    line_number: int
    event_type: str
    severity: Severity
    summary: str
    details: str
    resource: Optional[str] = None


class RemediationAction(BaseModel):
    """Concrete remediation step with command or patch."""
    action_type: str  # immediate_mitigation, permanent_fix, preventive_measure
    description: str
    kubectl_command: Optional[str] = None
    yaml_patch: Optional[str] = None
    explanation: str = ""


class RootCause(BaseModel):
    """Primary identified root cause with causal chain."""
    category: FailureCategory
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    causal_chain: List[str] = Field(default_factory=list)
    contributing_factors: List[str] = Field(default_factory=list)
    primary_finding_id: Optional[str] = None


class BlastRadius(BaseModel):
    """Estimated impact of the issue."""
    pods_affected: List[str] = Field(default_factory=list)
    containers_affected: List[str] = Field(default_factory=list)
    namespaces_affected: List[str] = Field(default_factory=list)
    nodes_affected: List[str] = Field(default_factory=list)
    services_affected: List[str] = Field(default_factory=list)
    estimated_service_impact: str = "Unknown"


class InvestigationReport(BaseModel):
    """Comprehensive investigation report."""
    investigation_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_log_lines: int
    parsed_entries: int
    execution_time_seconds: float
    overall_status: str = "COMPLETED"  # CRITICAL_FAILURE, DEGRADED, HEALTHY, INCONCLUSIVE
    
    root_cause: Optional[RootCause] = None
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)
    findings: List[Finding] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    remediations: List[RemediationAction] = Field(default_factory=list)
    
    # Optional LLM-generated synthesis / commentary
    ai_synthesis: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
