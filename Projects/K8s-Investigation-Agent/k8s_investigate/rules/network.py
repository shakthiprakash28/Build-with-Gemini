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
    # Service Endpoints & Unhealthy Routing
    re.compile(r"no endpoints available for service\s+['\"]?([a-zA-Z0-9_\-\./]+)['\"]?", re.IGNORECASE),
    re.compile(r"Endpoints:\s*<none>", re.IGNORECASE),
    re.compile(r"service\s+['\"]?([a-zA-Z0-9_\-\./]+)['\"]?\s+has no (?:active )?endpoints", re.IGNORECASE),
    re.compile(r"publishNotReadyAddresses\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r"routing (?:live )?traffic to (?:unready|unhealthy) (?:pod|endpoint)\s*([a-zA-Z0-9_\-\.:/]+)?", re.IGNORECASE),

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
    title = "Network, Service Endpoint, DNS, or TCP Connection Failure"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        subtypes = set()
        hosts_failed = set()
        details = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            # Do not treat kubelet probe lines as upstream network failures
            if re.search(r"(?:Liveness|Readiness|Startup)\s+probe\s+failed:", text, re.IGNORECASE):
                continue

            for pattern in NETWORK_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    low_str = matched_str.lower()
                    params: Dict[str, Any] = {}

                    if "no endpoints" in low_str or "endpoints:" in low_str or "no active endpoints" in low_str:
                        subtypes.add("SERVICE_NO_ENDPOINTS")
                        params["network_subsystem"] = "SERVICE_NO_ENDPOINTS"
                    elif "publishnotreadyaddresses" in low_str or "unready" in low_str or "unhealthy" in low_str:
                        subtypes.add("SERVICE_ROUTES_UNHEALTHY_PODS")
                        params["network_subsystem"] = "SERVICE_ROUTES_UNHEALTHY_PODS"
                    elif "udp" in low_str or "dns" in low_str or "nxdomain" in low_str or "lookup" in low_str:
                        subtypes.add("DNS_FAILURE")
                        params["network_subsystem"] = "DNS"
                    elif "x509" in low_str or "certificate" in low_str or "tls" in low_str:
                        subtypes.add("TLS_CERTIFICATE_ERROR")
                        params["network_subsystem"] = "TLS"
                    elif "refused" in low_str or "reset" in low_str or "upstream connect error" in low_str:
                        subtypes.add("TCP_CONNECTION_REFUSED")
                        params["network_subsystem"] = "TCP"
                    elif "timeout" in low_str or "timed out" in low_str:
                        subtypes.add("CONNECTION_TIMEOUT")
                        params["network_subsystem"] = "TIMEOUT"

                    if match.groups():
                        for g in match.groups():
                            if g and any(c in g for c in [".", ":", "-", "/"]):
                                hosts_failed.add(g)
                                params["endpoint"] = g

                    reason = f"Network/Service error detected: '{matched_str}'"
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
        endpoints_str = f" Targeted endpoints/services: {', '.join(sorted(hosts_failed))}." if hosts_failed else ""

        if "SERVICE_NO_ENDPOINTS" in subtypes:
            title = "Kubernetes Service Has No Active Endpoints"
            description = (
                f"A Kubernetes Service has zero ready backing pod endpoints [{subtypes_str}].{endpoints_str} "
                f"This typically occurs when Service label selectors do not match pod labels, or all backing pods are failing readiness checks."
            )
        elif "SERVICE_ROUTES_UNHEALTHY_PODS" in subtypes:
            title = "Service Routing Traffic to Unhealthy / Unready Pods"
            description = (
                f"Kubernetes Service is forwarding live traffic to pods that are unhealthy or not ready [{subtypes_str}].{endpoints_str} "
                f"This is caused by missing `readinessProbe` definitions, `publishNotReadyAddresses: true`, or shallow readiness checks."
            )
        else:
            title = "Network / DNS Resolution / TCP Connection Failure"
            description = (
                f"Network communication failure detected [{subtypes_str}].{endpoints_str} "
                f"The application is unable to reach required upstream services, resolve domain names, or complete secure handshakes."
            )

        remediations = []
        if "SERVICE_NO_ENDPOINTS" in subtypes:
            remediations.extend([
                "Inspect Service endpoints and selector labels: `kubectl describe svc <service-name>` and `kubectl get endpoints <service-name>`.",
                "Compare Service selector labels against pod labels: `kubectl get pods --show-labels`.",
            ])
        if "SERVICE_ROUTES_UNHEALTHY_PODS" in subtypes:
            remediations.extend([
                "Add or fix the container `readinessProbe` so kube-proxy removes unready pods from Service Endpoints before they receive traffic.",
                "Ensure `publishNotReadyAddresses` is set to `false` on the Service unless headless peer discovery is strictly required.",
            ])
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

        if "SERVICE_NO_ENDPOINTS" in subtypes:
            primary_subsystem = "SERVICE_NO_ENDPOINTS"
        elif "SERVICE_ROUTES_UNHEALTHY_PODS" in subtypes:
            primary_subsystem = "SERVICE_ROUTES_UNHEALTHY_PODS"
        elif "DNS_FAILURE" in subtypes:
            primary_subsystem = "DNS"
        elif "TLS_CERTIFICATE_ERROR" in subtypes:
            primary_subsystem = "TLS"
        elif "TCP_CONNECTION_REFUSED" in subtypes:
            primary_subsystem = "TCP"
        elif "CONNECTION_TIMEOUT" in subtypes:
            primary_subsystem = "TIMEOUT"
        else:
            primary_subsystem = sorted(list(subtypes))[0] if subtypes else "NETWORK"

        return Finding(
            id=self.rule_id,
            category=self.category,
            title=title,
            severity=Severity.HIGH,
            description=description,
            confidence=0.95,
            primary_indicator=details[0] if details else "Network Failure",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
            metadata={"network_subsystem": primary_subsystem, "subtypes": sorted(list(subtypes))},
        )
