"""
Rule Registry for Kubernetes Investigation Agent.
Aggregates and instantiates all diagnostic rules.
"""

from __future__ import annotations

from typing import List
from k8s_investigate.rules.base import DiagnosticRule
from k8s_investigate.rules.oom import OOMKillRule
from k8s_investigate.rules.crashloop import CrashLoopRule
from k8s_investigate.rules.probe import ProbeFailureRule
from k8s_investigate.rules.network import NetworkFailureRule
from k8s_investigate.rules.image_pull import ImagePullRule
from k8s_investigate.rules.storage import StorageRule
from k8s_investigate.rules.scheduling import SchedulingRule
from k8s_investigate.rules.rbac import RBACRule
from k8s_investigate.rules.application import ApplicationPanicRule


def get_default_rules() -> List[DiagnosticRule]:
    """Returns an ordered list of all default diagnostic rules."""
    return [
        OOMKillRule(),
        CrashLoopRule(),
        ProbeFailureRule(),
        NetworkFailureRule(),
        ImagePullRule(),
        StorageRule(),
        SchedulingRule(),
        RBACRule(),
        ApplicationPanicRule(),
    ]
