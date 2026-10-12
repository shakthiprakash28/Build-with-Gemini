"""
Diagnostic rules package for Kubernetes failure modes.
"""

from k8s_investigate.rules.base import DiagnosticRule
from k8s_investigate.rules.registry import get_default_rules

__all__ = ["DiagnosticRule", "get_default_rules"]
