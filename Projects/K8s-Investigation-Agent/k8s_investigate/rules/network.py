"""
Diagnostic rule for Network, DNS, Connection, and TLS failures in Kubernetes.
Detects CoreDNS timeouts/NXDOMAIN, TCP connection refused, connection reset by peer,
TLS/x509 certificate errors, and Envoy/Ingress 502/504 proxy errors.
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


NETWORK_PATTERNS = [
    # DNS
    re.compile(r"dial udp\s+([0-9\.:]+):53:\s*i/o timeout", re.IGNORECASE),
    re.compile(r"lookup\s+([a-zA-Z0-9_\-\.]+)(?:\s+on\s+[0-9\.:]+)?:\s*no such host", re.IGNORECASE),
    re.compile(r"server can't find\s+([a-zA-Z0-9_\-\.]+):\s*NXDOMAIN", re.IGNORECASE),
    re.compile(r"getaddrinfo\s*[:\s]*(?:EAI_NONAME|EAI_AGAIN|Name or service not known)", re.IGNORECASE),
    re.compile(r"dns resolution failed for\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
    
    # TCP / Connection
    re.compile(r"dial tcp\s+([0-9\.:]+):\s*connect:\s*(connection refused|i/o timeout|connection timed out)", re.IGNORECASE),
    re.compile(r"connect\(\)\s+failed\s+\(111:\s*Connection refused\)", re.IGNORECASE),
    re.compile(r"read:\s*connection reset by peer", re.IGNORECASE),
    re.compile(r"connection\s+reset\s+by\s+peer", re.IGNORECASE),
    re.compile(r"\bECONNREFUSED\b", re.IGNORECASE),
    re.compile(r"\bECONNRESET\b", re.IGNORECASE),
    re.compile(r"\bETIMEDOUT\b", re.IGNORECASE),
    re.compile(r"upstream connect error or disconnect/reset before headers", re.IGNORECASE),
    
    # TLS
    re.compile(r"x509:\s*certificate signed by unknown authority", re.IGNORECASE),
    re.compile(r"x509:\s*certificate has expired or is not yet valid", re.IGNORECASE),
    re.compile(r"SSL:\s*CERTIFICATE_VERIFY_FAILED", re.IGNORECASE),
    re.compile(r"remote error:\s*tls:\s*bad certificate", re.IGNORECASE),
]


class NetworkFailureRule(DiagnosticRule):
    rule_id = "RULE_K8S_NETWORK_DNS_FAILURE"
    category = FailureCategory.NETWORK_DNS_FAILURE
    title = "Network, DNS Resolution, or TCP Connection Failure"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        subtypes = set()
        hosts_failed = set()
        details = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in NETWORK_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    if "udp" in matched_str.lower() or "dns" in matched_str.lower() or "nxdomain" in matched_str.lower() or "lookup" in matched_str.lower():
                        subtypes.add("DNS_FAILURE")
                        params["network_subsystem"] = "DNS"
                    elif "x509" in matched_str.lower() or "certificate" in matched_str.lower() or "tls" in matched_str.lower():
                        subtypes.add("TLS_CERTIFICATE_ERROR")
                        params["network_subsystem"] = "TLS"
                    elif "refused" in matched_str.lower() or "reset" in matched_str.lower():
                        subtypes.add("TCP_CONNECTION_REFUSED")
                        params["network_subsystem"] = "TCP"
                    elif "timeout" in matched_str.lower() or "timed out" in matched_str.lower():
                        subtypes.add("CONNECTION_TIMEOUT")
                        params["network_subsystem"] = "TIMEOUT"

                    if match.groups():
                        for g in match.groups():
                            if g and any(c in g for c in [".", ":"]):
                                hosts_failed.add(g)
                                params["endpoint"] = g

                    reason = f"Network/DNS error detected: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    details.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        # Build description
        subtypes_str = ", ".join(sorted(subtypes))
        endpoints_str = f" Targeted endpoints/hosts: {', '.join(sorted(hosts_failed))}." if hosts_failed else ""

        description = (
            f"Network communication failure detected [{subtypes_str}].{endpoints_str} "
            f"The application is unable to reach required upstream services, resolve domain names, or complete secure handshakes."
        )

        remediations = []
        if "DNS_FAILURE" in subtypes:
            remediations.extend([
                "Check CoreDNS health and logs: `kubectl -n kube-system logs -l k8s-app=kube-dns`.",
                "Verify DNS search domain and ndots configuration in `/etc/resolv.conf` (pod `dnsConfig`).",
                "Ensure target service name conforms to Kubernetes FQDN: `<service>.<namespace>.svc.cluster.local`.",
            ])
        if "TCP_CONNECTION_REFUSED" in subtypes:
            remediations.extend([
                "Verify whether the target pod/service is running and actively listening on the target port.",
                "Check Kubernetes Endpoints: `kubectl get endpoints <service-name>` (empty endpoints mean target pods failed readiness).",
                "Inspect Kubernetes NetworkPolicy rules that may be blocking ingress/egress between namespaces.",
            ])
        if "TLS_CERTIFICATE_ERROR" in subtypes:
            remediations.extend([
                "Inspect TLS secrets and certificates for expiration dates: `openssl x509 -in tls.crt -noout -dates`.",
                "Verify trust bundle / CA configuration: ensure the issuing root CA is mounted in the container's trusted certs path.",
            ])
        if "CONNECTION_TIMEOUT" in subtypes:
            remediations.extend([
                "Check for node-level iptables or IPVS connection tracking (conntrack) table exhaustion: `sudo conntrack -C`.",
                "Verify cloud security groups, VPC peering routes, or egress firewall rules.",
            ])

        return Finding(
            id=self.rule_id,
            category=self.category,
            title="Network / DNS Resolution / TCP Connection Failure",
            severity=Severity.HIGH,
            description=description,
            confidence=0.92,
            primary_indicator=details[0] if details else "Network Failure",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
