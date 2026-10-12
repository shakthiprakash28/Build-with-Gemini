"""
Tests for Individual Diagnostic Rules.
"""

from k8s_investigate.parser import LogParser
from k8s_investigate.rules.oom import OOMKillRule
from k8s_investigate.rules.crashloop import CrashLoopRule
from k8s_investigate.rules.probe import ProbeFailureRule
from k8s_investigate.rules.network import NetworkFailureRule
from k8s_investigate.rules.image_pull import ImagePullRule
from k8s_investigate.rules.rbac import RBACRule
from k8s_investigate.rules.storage import StorageRule
from k8s_investigate.rules.scheduling import SchedulingRule
from k8s_investigate.models import FailureCategory, Severity


def test_oom_rule_detection():
    rule = OOMKillRule()
    parser = LogParser()
    logs = """
2026-10-10T00:14:02.110Z stderr F java.lang.OutOfMemoryError: Java heap space
2026-10-10T00:14:02.800Z stderr F cgroup out of memory: Killed process 412 (java)
2026-10-10T00:14:03.500Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Container terminated with exit code 137.
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.OOM_KILL
    assert finding.severity == Severity.CRITICAL
    assert len(finding.evidence) >= 1
    assert any("limit" in ev.extracted_params for ev in finding.evidence)


def test_crashloop_rule_detection():
    rule = CrashLoopRule()
    parser = LogParser()
    logs = """
2026-10-10T00:14:15.000Z stderr F Warning BackOff Back-off restarting failed container payment-app in pod payment-service-7d84bf9bc-5k9lm
2026-10-10T00:14:20.000Z stderr F Error: failed to start container: terminated with exit code 1
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.CRASH_LOOP
    assert len(finding.evidence) >= 1


def test_probe_rule_detection():
    rule = ProbeFailureRule()
    parser = LogParser()
    logs = """
2026-10-10T00:20:22.000Z stderr F Warning Unhealthy Liveness probe failed: HTTP probe failed with statuscode: 503
2026-10-10T00:20:24.000Z stderr F Warning Unhealthy Readiness probe failed: HTTP probe failed with statuscode: 503
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.PROBE_FAILURE
    assert len(finding.evidence) == 2


def test_network_dns_rule_detection():
    rule = NetworkFailureRule()
    parser = LogParser()
    logs = """
2026-10-10T00:20:15.890Z stderr F [ERROR] dial udp 10.96.0.10:53: i/o timeout while resolving postgres.svc.cluster.local
2026-10-10T00:20:18.000Z stderr F [ERROR] server can't find postgres.svc.cluster.local: NXDOMAIN
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.NETWORK_DNS_FAILURE
    assert len(finding.evidence) >= 1


def test_image_pull_rule_detection():
    rule = ImagePullRule()
    parser = LogParser()
    logs = """
2026-10-10T00:30:05.800Z stderr F Warning Failed Failed to pull image "myrepo/app:v1": unauthorized: authentication required
2026-10-10T00:30:20.000Z stderr F Warning Failed Error: ImagePullBackOff
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.IMAGE_PULL_FAILURE
    assert len(finding.evidence) >= 1


def test_rbac_rule_detection():
    rule = RBACRule()
    parser = LogParser()
    logs = """
2026-10-10T00:40:03.400Z stderr F [ERROR] secrets is forbidden: User "system:serviceaccount:monitoring:syncer" cannot list resource "secrets" in API group ""
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.RBAC_AUTH_FAILURE
    assert "monitoring/syncer" in finding.description or "syncer" in finding.description


def test_storage_rule_detection():
    rule = StorageRule()
    parser = LogParser()
    logs = """
2026-10-10T00:50:30.000Z stderr F Warning FailedAttachVolume Multi-Attach error for volume "pvc-12345" Volume is already exclusively attached
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.STORAGE_PVC_FAILURE


def test_scheduling_rule_detection():
    rule = SchedulingRule()
    parser = LogParser()
    logs = """
2026-10-10T00:50:00.000Z stderr F Warning FailedScheduling 0/3 nodes are available: 3 Insufficient memory.
"""
    entries = parser.parse_text(logs)
    finding = rule.evaluate(entries, {})

    assert finding is not None
    assert finding.category == FailureCategory.SCHEDULING_NODE_FAILURE
