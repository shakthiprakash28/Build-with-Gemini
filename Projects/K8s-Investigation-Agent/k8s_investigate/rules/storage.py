"""
Diagnostic rule for Storage, Persistent Volume (PV/PVC), and Volume Mount failures.
Detects Multi-Attach volume conflicts, FailedMount, VolumeBindingFailed, and filesystem permission issues.
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


STORAGE_PATTERNS = [
    re.compile(r"Multi-Attach error for volume\s+['\"]?([^'\"]+)['\"]?", re.IGNORECASE),
    re.compile(r"VolumeBindingFailed:\s*(.+)", re.IGNORECASE),
    re.compile(r"FailedMount:\s*(.+)", re.IGNORECASE),
    re.compile(r"FailedAttachVolume:\s*(.+)", re.IGNORECASE),
    re.compile(r"MountVolume\.SetUp failed for volume\s+['\"]?([^'\"]+)['\"]?:\s*(.+)", re.IGNORECASE),
    re.compile(r"persistentvolumeclaim\s+['\"]?([^'\"]+)['\"]?\s+not found", re.IGNORECASE),
    re.compile(r"Read-only file system", re.IGNORECASE),
    re.compile(r"chown:\s*(?:changing ownership of '[^']+':\s*)?Operation not permitted", re.IGNORECASE),
]


class StorageRule(DiagnosticRule):
    rule_id = "RULE_K8S_STORAGE_PVC_FAILURE"
    category = FailureCategory.STORAGE_PVC_FAILURE
    title = "Persistent Volume / Storage Mount Failure (FailedMount / Multi-Attach)"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        volumes = set()
        subtypes = set()
        reasons = []

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in STORAGE_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    if "multi-attach" in matched_str.lower():
                        subtypes.add("MULTI_ATTACH_CONFLICT")
                        params["storage_issue"] = "MULTI_ATTACH"
                    elif "volumebindingfailed" in matched_str.lower() or "not found" in matched_str.lower():
                        subtypes.add("PVC_UNBOUND_OR_MISSING")
                        params["storage_issue"] = "UNBOUND_PVC"
                    elif "read-only" in matched_str.lower() or "chown" in matched_str.lower():
                        subtypes.add("FS_PERMISSION_OR_CORRUPTION")
                        params["storage_issue"] = "PERMISSIONS"
                    else:
                        subtypes.add("MOUNT_FAILURE")
                        params["storage_issue"] = "MOUNT_FAILED"

                    if match.groups():
                        for g in match.groups():
                            if g and any(k in g for k in ["pvc-", "vol-", "disk", "data"]):
                                volumes.add(g.strip())
                                params["volume"] = g.strip()

                    reason = f"Storage/Volume failure detected: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        vols_str = f" Volumes involved: {', '.join(sorted(volumes))}." if volumes else ""
        subtypes_str = ", ".join(sorted(subtypes))

        description = (
            f"Storage and persistent volume mount failure detected [{subtypes_str}].{vols_str} "
            f"The container cannot access required volumes and cannot start or write application data."
        )

        remediations = [
            "Check PVC and PV status: `kubectl get pvc,pv -A`.",
            "Describe the impacted PVC for provisioner events: `kubectl describe pvc <pvc-name>`.",
        ]
        if "MULTI_ATTACH_CONFLICT" in subtypes:
            remediations.extend([
                "Multi-Attach conflict indicates a ReadWriteOnce volume is still attached to an old node. Verify if previous pod was forcefully terminated without proper detachment.",
                "Force detachment or wait for the volume-attachment controller timeout: `kubectl get volumeattachment`.",
            ])
        if "PVC_UNBOUND_OR_MISSING" in subtypes:
            remediations.extend([
                "Verify that the requested StorageClass exists and has an active CSI provisioner (`kubectl get sc`).",
                "Ensure sufficient disk capacity in the storage pool.",
            ])
        if "FS_PERMISSION_OR_CORRUPTION" in subtypes:
            remediations.extend([
                "Configure `securityContext.fsGroup` in pod spec so the container user has read/write ownership of mounted volumes.",
                "Verify if the underlying cloud disk is healthy or mounted read-only due to underlying filesystem errors.",
            ])

        return Finding(
            id=self.rule_id,
            category=self.category,
            title="Kubernetes Storage / Volume Mount Failure",
            severity=Severity.HIGH,
            description=description,
            confidence=0.94,
            primary_indicator=reasons[0] if reasons else "Storage Failure",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
