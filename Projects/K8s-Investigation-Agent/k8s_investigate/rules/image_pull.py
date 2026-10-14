"""
Diagnostic rule for ImagePullBackOff, ErrImagePull, and container registry authentication errors.
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


IMAGE_PATTERNS = [
    re.compile(r"\bImagePullBackOff\b", re.IGNORECASE),
    re.compile(r"\bErrImagePull\b", re.IGNORECASE),
    re.compile(r"Failed to pull image\s+['\"]?([^'\"]+)['\"]?:\s*(.+)", re.IGNORECASE),
    re.compile(r"rpc error: code = Unknown desc = Error response from daemon:\s*(.+)", re.IGNORECASE),
    re.compile(r"pull access denied for\s+([^,]+),\s+repository does not exist or may require 'docker login'", re.IGNORECASE),
    re.compile(r"toomanyrequests:\s*You have reached your pull rate limit", re.IGNORECASE),
    re.compile(r"manifest for\s+([^:]+:[^\s]+)\s+not found", re.IGNORECASE),
    re.compile(r"unauthorized:\s*authentication required", re.IGNORECASE),
    re.compile(r"trying and failing to pull image", re.IGNORECASE),
]


class ImagePullRule(DiagnosticRule):
    rule_id = "RULE_K8S_IMAGE_PULL_FAILURE"
    category = FailureCategory.IMAGE_PULL_FAILURE
    title = "Container Image Pull Failure (ImagePullBackOff / ErrImagePull)"
    default_severity = Severity.HIGH

    def evaluate(self, entries: List[LogEntry], context: Dict[str, Any]) -> Optional[Finding]:
        evidence_snippets: List[EvidenceSnippet] = []
        impacted_pods = set()
        failed_images = set()
        reasons = []
        is_auth_error = False
        is_rate_limited = False
        is_not_found = False

        for entry in entries:
            text = f"{entry.message} {entry.raw}"
            for pattern in IMAGE_PATTERNS:
                match = pattern.search(text)
                if match:
                    matched_str = match.group(0)
                    params: Dict[str, Any] = {}

                    if "pull access denied" in matched_str.lower() or "unauthorized" in matched_str.lower() or "authentication required" in matched_str.lower():
                        is_auth_error = True
                        params["failure_type"] = "AUTHENTICATION_FAILED"
                    elif "toomanyrequests" in matched_str.lower() or "rate limit" in matched_str.lower():
                        is_rate_limited = True
                        params["failure_type"] = "RATE_LIMIT_EXCEEDED"
                    elif "not found" in matched_str.lower() or "manifest" in matched_str.lower():
                        is_not_found = True
                        params["failure_type"] = "MANIFEST_NOT_FOUND"

                    if match.groups():
                        img_cand = match.group(1)
                        if img_cand and len(img_cand) > 3 and not img_cand.startswith("rpc error"):
                            failed_images.add(img_cand.strip())
                            params["image"] = img_cand.strip()

                    reason = f"Image pull error: '{matched_str}'"
                    snippet = self.extract_evidence_snippet(entry, entries, reason=reason, params=params)
                    evidence_snippets.append(snippet)

                    if entry.pod:
                        impacted_pods.add(entry.pod)
                    reasons.append(matched_str)
                    break

        if not evidence_snippets:
            return None

        images_str = f" Target image(s): {', '.join(sorted(failed_images))}." if failed_images else ""
        description = (
            f"Kubelet failed to pull the specified container image{images_str} "
            f"The pod cannot transition into 'Running' status and is stuck in ImagePullBackOff."
        )

        remediations = [
            "Verify image name and tag spelling in deployment/pod spec.",
            "Verify that the container image exists in the registry: `docker pull <image-name>` or crane/skopeo inspect.",
        ]
        if is_auth_error:
            remediations.extend([
                "Authentication failure: Create or update `imagePullSecrets`: `kubectl create secret docker-registry regcred --docker-server=<server> --docker-username=<user> --docker-password=<pass>`.",
                "Attach secret to the pod spec under `spec.imagePullSecrets` or link it to the default ServiceAccount.",
            ])
        if is_rate_limited:
            remediations.append("Registry rate limit reached (e.g. Docker Hub anonymous tier). Configure authenticated pull secrets or mirror images to private registry (e.g. Artifact Registry, ECR, Harbor).")
        if is_not_found:
            remediations.append("Image tag or digest does not exist in the remote registry. Check CI/CD build output to ensure image tag was published.")

        return Finding(
            id=self.rule_id,
            category=self.category,
            title="ImagePullBackOff / ErrImagePull Detected",
            severity=Severity.HIGH,
            description=description,
            confidence=0.96,
            primary_indicator=reasons[0] if reasons else "ImagePullBackOff",
            evidence=evidence_snippets,
            impacted_resources=sorted(list(impacted_pods)),
            suggested_remediation=remediations,
        )
