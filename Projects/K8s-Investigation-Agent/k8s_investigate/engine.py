"""
Core Investigation Engine.
Executes diagnostic rules, reconstructs chronological incident timelines,
performs causal correlation to isolate Root Cause vs Secondary Cascades,
and produces concrete actionable remediation plans.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
from k8s_investigate.rules.base import DiagnosticRule
from k8s_investigate.rules.registry import get_default_rules


class InvestigationEngine:
    """Orchestrates log diagnostics, causality resolution, timeline construction, and reporting."""

    def __init__(self, rules: Optional[List[DiagnosticRule]] = None):
        self.rules = rules or get_default_rules()

    def analyze(self, entries: List[LogEntry], context: Optional[Dict[str, Any]] = None) -> InvestigationReport:
        """Executes full diagnostic pipeline over normalized log entries."""
        start_time = datetime.now(timezone.utc)
        context = context or {}

        # 1. Run all diagnostic rules
        findings: List[Finding] = []
        for rule in self.rules:
            try:
                finding = rule.evaluate(entries, context)
                if finding:
                    findings.append(finding)
            except Exception as e:
                # Keep investigation resilient
                context.setdefault("rule_errors", []).append(f"Rule {rule.rule_id} failed: {e}")

        # 2. Build Chronological Timeline
        timeline = self._build_timeline(entries, findings)

        # 3. Determine Root Cause and Causal Cascade
        root_cause = self._determine_root_cause(findings, timeline, entries)
        if root_cause and context.get("version_change_analysis"):
            v_info = context["version_change_analysis"]
            summary_note = v_info.get("summary")
            if summary_note and summary_note not in root_cause.contributing_factors:
                if v_info.get("version_changed"):
                    root_cause.contributing_factors.insert(0, summary_note)
                    if summary_note not in root_cause.causal_chain:
                        root_cause.causal_chain.insert(0, summary_note)
                else:
                    root_cause.contributing_factors.append(summary_note)

        # 4. Compute Blast Radius
        blast_radius = self._compute_blast_radius(entries, findings)

        # 5. Generate Concrete Remediation Actions
        remediations = self._generate_remediations(root_cause, findings, blast_radius, context=context)

        # Determine overall status
        if any(f.severity == Severity.CRITICAL for f in findings):
            overall_status = "CRITICAL_FAILURE"
        elif any(f.severity == Severity.HIGH for f in findings):
            overall_status = "HIGH_SEVERITY_INCIDENT"
        elif findings:
            overall_status = "DEGRADED_STATE"
        else:
            overall_status = "HEALTHY_OR_INCONCLUSIVE"

        end_time = datetime.now(timezone.utc)
        exec_seconds = (end_time - start_time).total_seconds()

        return InvestigationReport(
            investigation_id=f"k8s-inv-{uuid.uuid4().hex[:8]}",
            generated_at=end_time,
            total_log_lines=entries[-1].line_number if entries else 0,
            parsed_entries=len(entries),
            execution_time_seconds=round(exec_seconds, 4),
            overall_status=overall_status,
            root_cause=root_cause,
            blast_radius=blast_radius,
            findings=findings,
            timeline=timeline,
            remediations=remediations,
        )

    def _build_timeline(self, entries: List[LogEntry], findings: List[Finding]) -> List[TimelineEvent]:
        """Constructs an ordered chronological timeline of critical events."""
        events: List[TimelineEvent] = []

        # Find significant entries (errors, warnings, state changes)
        for entry in entries:
            is_significant = False
            summary = ""
            event_type = "LOG_EVENT"
            sev = Severity.INFO

            if entry.level in ["FATAL", "CRITICAL"]:
                is_significant = True
                sev = Severity.CRITICAL
                event_type = "FATAL_ERROR"
                summary = entry.message[:90]
            elif entry.level == "ERROR":
                is_significant = True
                sev = Severity.HIGH
                event_type = "ERROR"
                summary = entry.message[:90]
            elif entry.metadata.get("event_type") == "Warning":
                is_significant = True
                sev = Severity.MEDIUM
                event_type = f"K8S_{entry.metadata.get('event_reason', 'WARNING')}".upper()
                summary = entry.message[:90]

            if is_significant:
                events.append(TimelineEvent(
                    timestamp=entry.timestamp,
                    relative_time_str=entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else f"Line {entry.line_number}",
                    line_number=entry.line_number,
                    event_type=event_type,
                    severity=sev,
                    summary=summary.strip(),
                    details=entry.message.strip(),
                    resource=entry.pod or entry.container,
                ))

        # Sort timeline: if timestamps exist, sort by timestamp; else sort by line_number
        has_timestamps = any(e.timestamp is not None for e in events)
        if has_timestamps:
            # Sort none-timestamps to end while keeping relative order
            events.sort(key=lambda x: (x.timestamp is None, x.timestamp, x.line_number))
        else:
            events.sort(key=lambda x: x.line_number)

        # Deduplicate and limit timeline to the most relevant max 20 events
        filtered_events: List[TimelineEvent] = []
        last_summary = None
        for ev in events:
            if ev.summary != last_summary:
                filtered_events.append(ev)
                last_summary = ev.summary
            if len(filtered_events) >= 25:
                break

        return filtered_events

    def _determine_root_cause(
        self,
        findings: List[Finding],
        timeline: List[TimelineEvent],
        entries: List[LogEntry],
    ) -> Optional[RootCause]:
        """
        Infers the primary root cause by resolving causal dependencies across findings.
        Distinguishes primary triggers from cascade symptoms.
        """
        if not findings:
            return None

        categories = {f.category: f for f in findings}

        # Causal Hierarchy:
        # 1. External/Cluster blockers (Scheduling, RBAC, Storage, Image Pull)
        # 2. In-Pod Fatal Resource limits (OOM_KILL)
        # 3. Network / Dependency timeouts (CoreDNS, DB timeouts)
        # 4. Probes (Probe Failure)
        # 5. Generic Symptoms (CrashLoopBackOff, Application Panic)

        # Case 1: OOMKilled + CrashLoopBackOff
        if FailureCategory.OOM_KILL in categories and FailureCategory.CRASH_LOOP in categories:
            oom_finding = categories[FailureCategory.OOM_KILL]
            return RootCause(
                category=FailureCategory.OOM_KILL,
                summary="Container Out-Of-Memory (OOMKilled) triggered CrashLoopBackOff restart cycles.",
                confidence=0.98,
                severity=Severity.CRITICAL,
                causal_chain=[
                    "Container memory usage exceeded cgroup limit",
                    "Linux kernel / kubelet invoked OOM Killer and dispatched SIGKILL (exit code 137)",
                    "Container exited abruptly",
                    "Kubelet repeatedly restarted container, entering CrashLoopBackOff",
                ],
                contributing_factors=[
                    "Inadequate memory limits set in pod specification",
                    "Memory leak or high concurrency traffic spike in application code",
                ],
                primary_finding_id=oom_finding.id,
            )

        # Case 2: Network / DNS Failure -> Probe Failure -> CrashLoop
        if FailureCategory.NETWORK_DNS_FAILURE in categories and (
            FailureCategory.PROBE_FAILURE in categories or FailureCategory.CRASH_LOOP in categories
        ):
            net_finding = categories[FailureCategory.NETWORK_DNS_FAILURE]
            return RootCause(
                category=FailureCategory.NETWORK_DNS_FAILURE,
                summary="Network/DNS connection failure prevented health probes and caused service outage.",
                confidence=0.94,
                severity=Severity.HIGH,
                causal_chain=[
                    "Application failed to resolve upstream host or establish TCP connection (timeout/refused)",
                    "Internal health checks or background workers failed",
                    "Kubernetes Liveness/Readiness probes timed out or returned HTTP 5xx",
                    "Kubelet failed container health checks and initiated termination/restart",
                ],
                contributing_factors=[
                    "CoreDNS resolution failure or search domain exhaustion",
                    "Downstream database/service outage or missing NetworkPolicy egress rule",
                ],
                primary_finding_id=net_finding.id,
            )

        # Case 3: RBAC Failure -> CrashLoop / App Failure
        if FailureCategory.RBAC_AUTH_FAILURE in categories:
            rbac_finding = categories[FailureCategory.RBAC_AUTH_FAILURE]
            return RootCause(
                category=FailureCategory.RBAC_AUTH_FAILURE,
                summary="Missing Kubernetes RBAC permissions caused pod process to fail initialization.",
                confidence=0.97,
                severity=Severity.HIGH,
                causal_chain=[
                    "Application attempted Kubernetes API call on startup",
                    "API server rejected request with 403 Forbidden due to missing Role/ClusterRole",
                    "Application process panicked or exited with fatal error",
                    "Kubelet marked pod as CrashLoopBackOff",
                ],
                contributing_factors=[
                    "ServiceAccount not granted necessary permissions for target API resource",
                    "Pod deployed with default ServiceAccount lacking required roles",
                ],
                primary_finding_id=rbac_finding.id,
            )

        # Case 4: Image Pull Failure
        if FailureCategory.IMAGE_PULL_FAILURE in categories:
            img_finding = categories[FailureCategory.IMAGE_PULL_FAILURE]
            has_not_found = any(
                any(kw in line.lower() for kw in ["not found", "manifest unknown", "failed to resolve reference", "rpc error: code = notfound"] for line in ev.raw_lines)
                for ev in img_finding.evidence
            )
            if has_not_found:
                summary = "Container image tag or repository does not exist in registry (ImagePullBackOff / 404 Not Found)."
                causal_chain = [
                    "Kubelet received pod specification requesting container image",
                    "Kubelet contacted remote container registry to resolve image manifest",
                    "Registry rejected request with 'Not Found' (tag or repository does not exist)",
                    "Kubelet marked container state as ErrImagePull and backed off with ImagePullBackOff",
                ]
                contributing_factors = [
                    "Typo or invalid tag version in container image specification",
                    "CI/CD pipeline failed to push container image before pod creation",
                ]
                confidence = 0.98
            else:
                summary = "Container image could not be pulled from registry (ImagePullBackOff / ErrImagePull)."
                causal_chain = [
                    "Kubelet attempted to pull container image from remote registry",
                    "Registry rejected request (authentication required, rate limit, or invalid tag)",
                    "Pod remained in Waiting state with ImagePullBackOff",
                ]
                contributing_factors = [
                    "Missing or expired imagePullSecrets",
                    "Typo in image tag or repository URI",
                ]
                confidence = 0.96

            return RootCause(
                category=FailureCategory.IMAGE_PULL_FAILURE,
                summary=summary,
                confidence=confidence,
                severity=Severity.HIGH,
                causal_chain=causal_chain,
                contributing_factors=contributing_factors,
                primary_finding_id=img_finding.id,
            )

        # Case 5: Storage / PVC Mount Failure
        if FailureCategory.STORAGE_PVC_FAILURE in categories:
            storage_finding = categories[FailureCategory.STORAGE_PVC_FAILURE]
            return RootCause(
                category=FailureCategory.STORAGE_PVC_FAILURE,
                summary="Persistent Volume attachment or filesystem mount failed.",
                confidence=0.95,
                severity=Severity.HIGH,
                causal_chain=[
                    "Kubelet volume manager attempted to attach/mount volume to host node",
                    "Volume attachment failed (Multi-Attach conflict, missing PVC, or permission denied)",
                    "Container creation blocked at Setup phase",
                ],
                contributing_factors=[
                    "Volume already mounted in ReadWriteOnce mode to another node",
                    "Storage provisioner unavailable or storage class misconfigured",
                ],
                primary_finding_id=storage_finding.id,
            )

        # Case 6: Scheduling Failure
        if FailureCategory.SCHEDULING_NODE_FAILURE in categories:
            sched_finding = categories[FailureCategory.SCHEDULING_NODE_FAILURE]
            return RootCause(
                category=FailureCategory.SCHEDULING_NODE_FAILURE,
                summary="Kubernetes scheduler could not assign pod to any node (Resource starvation / Taints).",
                confidence=0.96,
                severity=Severity.HIGH,
                causal_chain=[
                    "Pod created and submitted to kube-scheduler queue",
                    "Scheduler filtering evaluated all candidate nodes",
                    "0 nodes satisfied CPU, memory, or taint requirements",
                    "Pod stuck in Pending state",
                ],
                contributing_factors=[
                    "Node pool exhausted or pod resource requests set too high",
                    "Node taints missing corresponding tolerations",
                ],
                primary_finding_id=sched_finding.id,
            )

        # Default fallback: pick the finding with the highest severity
        sorted_findings = sorted(findings, key=lambda f: (f.severity.rank, f.confidence), reverse=True)
        top = sorted_findings[0]
        return RootCause(
            category=top.category,
            summary=top.title,
            confidence=top.confidence,
            severity=top.severity,
            causal_chain=[top.description],
            contributing_factors=["See detailed finding and evidence snippets below"],
            primary_finding_id=top.id,
        )

    def _compute_blast_radius(self, entries: List[LogEntry], findings: List[Finding]) -> BlastRadius:
        """Determines the scope and impacted resources of the incident."""
        pods = set()
        containers = set()
        namespaces = set()
        nodes = set()

        for entry in entries:
            if entry.pod:
                pods.add(entry.pod)
            if entry.container:
                containers.add(entry.container)
            if entry.namespace:
                namespaces.add(entry.namespace)
            if entry.node:
                nodes.add(entry.node)

        for finding in findings:
            for res in finding.impacted_resources:
                pods.add(res)

        pod_list = sorted(list(pods))
        impact_level = "Single Pod Affected" if len(pod_list) <= 1 else f"Multiple Pods Affected ({len(pod_list)} pods)"
        if not pod_list:
            impact_level = "Cluster/Node Component Level"

        return BlastRadius(
            pods_affected=pod_list,
            containers_affected=sorted(list(containers)),
            namespaces_affected=sorted(list(namespaces)),
            nodes_affected=sorted(list(nodes)),
            services_affected=[],
            estimated_service_impact=impact_level,
        )

    def _generate_remediations(
        self,
        root_cause: Optional[RootCause],
        findings: List[Finding],
        blast_radius: BlastRadius,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[RemediationAction]:
        """Generates structured remediation actions with copy-pasteable kubectl commands and patches."""
        actions: List[RemediationAction] = []
        target_pod = blast_radius.pods_affected[0] if blast_radius.pods_affected else "<pod-name>"

        if not root_cause:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Check cluster pod health and events.",
                kubectl_command=f"kubectl get pods -A -o wide",
                explanation="Inspect all pods across namespaces to identify failing workloads.",
            ))
            return actions

        cat = root_cause.category

        if cat == FailureCategory.OOM_KILL:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Increase container memory limits to restore service stability.",
                kubectl_command=f"kubectl set resources deployment/<deployment-name> --limits=memory=1Gi --requests=memory=512Mi",
                yaml_patch="""spec:
  template:
    spec:
      containers:
      - name: app
        resources:
          requests:
            memory: "512Mi"
          limits:
            memory: "1Gi" """,
                explanation="Prevents the Linux cgroup OOM killer from killing the process immediately upon memory spikes.",
            ))
            actions.append(RemediationAction(
                action_type="permanent_fix",
                description="Capture heap dumps or profile application memory usage.",
                kubectl_command=f"kubectl logs {target_pod} --previous | grep -i -E 'oom|memory|heap'",
                explanation="Identifies memory leaks, unclosed database connection pools, or runaway caching algorithms.",
            ))

        elif cat == FailureCategory.CRASH_LOOP:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Inspect the logs of the previous terminated container instance.",
                kubectl_command=f"kubectl logs {target_pod} --previous",
                explanation="Shows the exact stack trace or error message that occurred right before the container exited.",
            ))
            actions.append(RemediationAction(
                action_type="permanent_fix",
                description="Debug container interactively with an ephemeral container.",
                kubectl_command=f"kubectl debug -it {target_pod} --image=busybox --target=app",
                explanation="Allows inspecting the running filesystem, environment variables, and configuration files.",
            ))

        elif cat == FailureCategory.PROBE_FAILURE:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Increase probe timeout and failure threshold to prevent false restarts.",
                yaml_patch="""livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 5""",
                explanation="Gives the application more time to respond when undergoing high load or startup initialization.",
            ))
            actions.append(RemediationAction(
                action_type="permanent_fix",
                description="Introduce a startupProbe to protect long-starting applications.",
                yaml_patch="""startupProbe:
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 30
  periodSeconds: 10""",
                explanation="Ensures livenessProbe does not begin checking until the application is fully initialized.",
            ))

        elif cat == FailureCategory.NETWORK_DNS_FAILURE:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Verify CoreDNS pods health in kube-system namespace.",
                kubectl_command="kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide",
                explanation="Ensures cluster DNS pods are running and healthy.",
            ))
            actions.append(RemediationAction(
                action_type="permanent_fix",
                description="Test DNS resolution directly inside a cluster pod.",
                kubectl_command="kubectl run dns-test --rm -it --restart=Never --image=busybox -- nslookup kubernetes.default",
                explanation="Tests whether cluster DNS resolution functions from inside the pod network.",
            ))

        elif cat == FailureCategory.IMAGE_PULL_FAILURE:
            is_tag_not_found = False
            missing_img = None
            for f in findings:
                if f.category == FailureCategory.IMAGE_PULL_FAILURE:
                    for ev in f.evidence:
                        for line in ev.raw_lines:
                            if any(phrase in line.lower() for phrase in ["not found", "manifest unknown", "failed to resolve reference", "rpc error: code = notfound"]):
                                is_tag_not_found = True
                                img_match = re.search(r'image ["\']([^"\']+)["\']', line)
                                if img_match:
                                    missing_img = img_match.group(1)
                                break
                        if is_tag_not_found:
                            break

            if is_tag_not_found:
                container_name = blast_radius.containers_affected[0] if blast_radius.containers_affected else "<container-name>"
                img_desc = f" '{missing_img}'" if missing_img else ""
                actions.append(RemediationAction(
                    action_type="immediate_mitigation",
                    description="Verify image name/tag on registry and update pod image.",
                    kubectl_command=f"kubectl set image pod/{target_pod} {container_name}=<valid-image>:<tag>",
                    explanation=f"The requested image{img_desc} was not found on the registry. Confirm the correct tag on Docker Hub/registry and update the pod or deployment.",
                ))
                actions.append(RemediationAction(
                    action_type="permanent_fix",
                    description="Correct image tag in workload YAML manifest and re-apply.",
                    kubectl_command=f"kubectl describe pod {target_pod} | grep -i image",
                    explanation="Verify the image name in git manifests / Helm values matches your release artifacts.",
                ))
            else:
                actions.append(RemediationAction(
                    action_type="immediate_mitigation",
                    description="Verify image pull secret and create registry credential secret.",
                    kubectl_command="kubectl create secret docker-registry regcred --docker-server=<server> --docker-username=<user> --docker-password=<pass>",
                    explanation="Allows kubelet to authenticate against private container registries.",
                ))
                actions.append(RemediationAction(
                    action_type="permanent_fix",
                    description="Bind image pull secret to the pod or default service account.",
                    kubectl_command="kubectl patch serviceaccount default -p '{\"imagePullSecrets\": [{\"name\": \"regcred\"}]}'",
                    explanation="Automatically applies image pull credentials to all pods created in the namespace.",
                ))

        elif cat == FailureCategory.RBAC_AUTH_FAILURE:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Check what permissions the pod ServiceAccount is missing.",
                kubectl_command=f"kubectl auth can-i get pods --as=system:serviceaccount:default:default",
                explanation="Simulates API permissions to verify missing RBAC privileges.",
            ))
            actions.append(RemediationAction(
                action_type="permanent_fix",
                description="Apply Role and RoleBinding YAML manifest.",
                yaml_patch="""apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods
  namespace: default
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io""",
                explanation="Grants required API permissions to the ServiceAccount.",
            ))

        elif cat == FailureCategory.SCHEDULING_NODE_FAILURE:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Inspect node resource capacity and pod resource requests.",
                kubectl_command="kubectl describe nodes | grep -A 8 'Allocated resources'",
                explanation="Identifies which nodes have exhausted CPU or memory capacity.",
            ))

        elif cat == FailureCategory.STORAGE_PVC_FAILURE:
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description="Check PVC status and volume attachments.",
                kubectl_command="kubectl get pvc,pv,volumeattachment -A",
                explanation="Identifies stuck volume attachments and unbound PersistentVolumeClaims.",
            ))

        v_info = (context or {}).get("version_change_analysis")
        if v_info and v_info.get("version_changed"):
            deploy_name = v_info.get("deployment_name") or "<deployment-name>"
            prev_rev = v_info.get("previous_revision")
            undo_cmd = f"kubectl rollout undo deployment/{deploy_name}"
            if prev_rev:
                undo_cmd += f" --to-revision={prev_rev}"
            actions.append(RemediationAction(
                action_type="immediate_mitigation",
                description=f"Roll back deployment '{deploy_name}' to previous working version.",
                kubectl_command=undo_cmd,
                explanation=v_info.get("summary") or "Reverts the recent pod version/image rollout to restore stability.",
            ))

        return actions
