"""
Tests for Investigation Engine, Causality Determination, and Remediation.
"""

from k8s_investigate.engine import InvestigationEngine
from k8s_investigate.parser import LogParser
from k8s_investigate.models import FailureCategory, Severity


def test_causal_resolution_oom_over_crashloop():
    """Ensure OOM is isolated as Root Cause, with CrashLoopBackOff as cascade effect."""
    parser = LogParser()
    engine = InvestigationEngine()

    logs = """
2026-10-10T00:14:02.110Z stderr F java.lang.OutOfMemoryError: Java heap space
2026-10-10T00:14:02.800Z stderr F cgroup out of memory: Killed process 412 (java)
2026-10-10T00:14:03.500Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Container payment-app terminated with exit code 137.
2026-10-10T00:14:15.000Z stderr F Warning BackOff Back-off restarting failed container payment-app in pod payment-service-7d84bf9bc-5k9lm
"""
    entries = parser.parse_text(logs)
    report = engine.analyze(entries)

    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.OOM_KILL
    assert report.root_cause.severity == Severity.CRITICAL
    assert len(report.root_cause.causal_chain) > 1
    assert any("OOM" in step for step in report.root_cause.causal_chain)
    
    # Check that remediation includes memory limit adjustments
    assert any("memory" in rem.description.lower() for rem in report.remediations)
    assert any(rem.kubectl_command and "kubectl set resources" in rem.kubectl_command for rem in report.remediations)


def test_causal_resolution_dns_over_probe():
    """Ensure DNS failure is identified as Root Cause when probe fails due to connection drop."""
    parser = LogParser()
    engine = InvestigationEngine()

    logs = """
2026-10-10T00:20:15.890Z stderr F [ERROR] dial udp 10.96.0.10:53: i/o timeout while resolving postgres.svc.cluster.local
2026-10-10T00:20:18.000Z stderr F [ERROR] lookup postgres.svc.cluster.local on 10.96.0.10:53: no such host
2026-10-10T00:20:22.000Z stderr F Warning Unhealthy Liveness probe failed: HTTP probe failed with statuscode: 503
"""
    entries = parser.parse_text(logs)
    report = engine.analyze(entries)

    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.NETWORK_DNS_FAILURE
    assert any("CoreDNS" in rem.description or "DNS" in rem.description for rem in report.remediations)


def test_timeline_ordering():
    parser = LogParser()
    engine = InvestigationEngine()

    logs = """
2026-10-10T00:01:00Z stdout F [INFO] Starting up
2026-10-10T00:02:00Z stderr F [ERROR] First error occurred
2026-10-10T00:03:00Z stderr F [FATAL] Fatal crash occurred
"""
    entries = parser.parse_text(logs)
    report = engine.analyze(entries)

    assert len(report.timeline) == 2
    assert report.timeline[0].event_type == "ERROR"
    assert report.timeline[1].event_type == "FATAL_ERROR"
