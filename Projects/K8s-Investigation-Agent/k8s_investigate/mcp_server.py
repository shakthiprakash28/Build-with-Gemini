"""
Kubernetes MCP Server for remote cluster inspection and troubleshooting.

Runs inside the GKE cluster using in-cluster service account credentials (with fallback
to local kubeconfig) and exposes read-only Kubernetes diagnostic tools over MCP
Streamable HTTP (`/mcp`) so the Kubernetes Investigation Agent running on Vertex AI
Agent Runtime can remotely inspect and troubleshoot the cluster.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from starlette.requests import Request
from starlette.responses import JSONResponse

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover - fallback for mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # pragma: no cover
    TransportSecuritySettings = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

mcp = MCPServer(
    "k8s-mcp-server",
    instructions=(
        "Read-only Kubernetes MCP server running inside the GKE cluster. "
        "Provides tools to list namespaces and pods, inspect pod logs and container "
        "termination states, fetch pod/cluster events, inspect deployment revision "
        "history, and check cluster node health and resource pressure."
    ),
)


def _load_k8s_clients() -> Tuple[Any, Any]:
    """Loads Kubernetes in-cluster config (or local kubeconfig fallback) and returns (CoreV1Api, AppsV1Api)."""
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return client.CoreV1Api(), client.AppsV1Api()


def _format_age(ts: Optional[datetime]) -> str:
    """Formats a Kubernetes timestamp into a compact relative age string (e.g. '15m', '2h', '3d')."""
    if ts is None:
        return "<unknown>"
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = max(0, int((now - ts).total_seconds()))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86400:
        return f"{delta // 3600}h"
    return f"{delta // 86400}d"


def _normalize_target(name: str, namespace: str = "default") -> Tuple[str, str]:
    """Normalizes '<kind>/<name>' or '<namespace>/<name>' into (clean_name, clean_namespace)."""
    clean_name = (name or "").strip().strip("\"'`")
    clean_ns = (namespace or "default").strip().strip("\"'`") or "default"
    if "/" in clean_name:
        prefix, remainder = clean_name.split("/", 1)
        if prefix.lower() in (
            "pod",
            "pods",
            "deployment",
            "deployments",
            "deploy",
            "deployment.apps",
            "replicaset",
            "rs",
            "node",
            "nodes",
            "service",
            "svc",
        ):
            clean_name = remainder
        elif clean_ns == "default" and remainder:
            clean_ns = prefix
            clean_name = remainder
    return clean_name, clean_ns


def _resolve_pod_name(core_v1: Any, pod_or_prefix: str, namespace: str) -> str:
    """Resolves an exact pod name or deployment/prefix name to an existing Pod in the namespace."""
    from kubernetes.client.exceptions import ApiException

    try:
        core_v1.read_namespaced_pod(name=pod_or_prefix, namespace=namespace)
        return pod_or_prefix
    except ApiException as exc:
        if exc.status != 404:
            raise

    pods = core_v1.list_namespaced_pod(namespace=namespace).items
    matches = [
        p.metadata.name
        for p in pods
        if p.metadata.name == pod_or_prefix
        or p.metadata.name.startswith(f"{pod_or_prefix}-")
        or (p.metadata.labels and p.metadata.labels.get("app") == pod_or_prefix)
    ]
    if matches:
        return matches[0]
    return pod_or_prefix


def _format_pod_describe(pod: Any, events: List[Any]) -> str:
    """Formats a V1Pod and its V1Event list into a `kubectl describe pod`-compatible text block."""
    meta = pod.metadata
    spec = pod.spec
    status = pod.status

    node_str = spec.node_name or "<none>"
    if status and status.host_ip and spec.node_name:
        node_str = f"{spec.node_name}/{status.host_ip}"

    lines = [
        f"Name:             {meta.name}",
        f"Namespace:        {meta.namespace}",
        f"Node:             {node_str}",
        f"Status:           {status.phase if status else 'Unknown'}",
        f"IP:               {status.pod_ip if status and status.pod_ip else '<none>'}",
    ]

    if meta.owner_references:
        owners = ", ".join(f"{o.kind}/{o.name}" for o in meta.owner_references)
        lines.append(f"Controlled By:    {owners}")

    lines.append("Containers:")
    c_statuses = {cs.name: cs for cs in (status.container_statuses or [])} if status else {}

    for c in spec.containers or []:
        lines.append(f"  {c.name}:")
        lines.append(f"    Image:          {c.image}")
        cs = c_statuses.get(c.name)
        if cs:
            if cs.image_id:
                lines.append(f"    Image ID:       {cs.image_id}")
            lines.append(f"    Ready:          {cs.ready}")
            lines.append(f"    Restart Count:  {cs.restart_count}")

            if cs.state:
                if cs.state.waiting:
                    lines.append("    State:          Waiting")
                    lines.append(f"      Reason:       {cs.state.waiting.reason}")
                    if cs.state.waiting.message:
                        lines.append(f"      Message:      {cs.state.waiting.message}")
                elif cs.state.terminated:
                    lines.append("    State:          Terminated")
                    lines.append(f"      Reason:       {cs.state.terminated.reason}")
                    lines.append(f"      Exit Code:    {cs.state.terminated.exit_code}")
                    if cs.state.terminated.message:
                        lines.append(f"      Message:      {cs.state.terminated.message}")
                elif cs.state.running:
                    lines.append("    State:          Running")
                    lines.append(f"      Started:      {cs.state.running.started_at}")

            if cs.last_state and cs.last_state.terminated:
                lt = cs.last_state.terminated
                lines.append("    Last State:     Terminated")
                lines.append(f"      Reason:       {lt.reason}")
                lines.append(f"      Exit Code:    {lt.exit_code}")
                if lt.message:
                    lines.append(f"      Message:      {lt.message}")

        if c.resources:
            if c.resources.limits:
                lines.append("    Limits:")
                for k, v in c.resources.limits.items():
                    lines.append(f"      {k}:  {v}")
            if c.resources.requests:
                lines.append("    Requests:")
                for k, v in c.resources.requests.items():
                    lines.append(f"      {k}:  {v}")

    if status and status.conditions:
        lines.append("Conditions:")
        lines.append("  Type              Status  Reason")
        for cond in status.conditions:
            lines.append(f"  {cond.type:<18}{cond.status:<8}{cond.reason or ''}")

    lines.append("Events:")
    if not events:
        lines.append("  <none>")
    else:
        lines.append("  Type     Reason            Age    From               Message")
        lines.append("  ----     ------            ----   ----               -------")
        for ev in events:
            ev_ts = ev.last_timestamp or ev.event_time or (ev.metadata.creation_timestamp if ev.metadata else None)
            age = _format_age(ev_ts)
            src = ""
            if ev.source and ev.source.component:
                src = ev.source.component
            elif ev.reporting_component:
                src = ev.reporting_component
            lines.append(
                f"  {ev.type or 'Normal':<8} {ev.reason or '':<17} {age:<6} {src:<18} {ev.message or ''}"
            )

    return "\n".join(lines)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request: Request) -> JSONResponse:
    """Kubernetes liveness and readiness probe endpoint."""
    return JSONResponse({"status": "healthy", "service": "k8s-mcp-server"})


@mcp.tool()
def list_namespaces() -> str:
    """List all Kubernetes namespaces in the GKE cluster and their status."""
    core_v1, _ = _load_k8s_clients()
    namespaces = core_v1.list_namespace().items
    lines = ["NAME                     STATUS    AGE"]
    for ns in namespaces:
        name = ns.metadata.name
        phase = ns.status.phase if ns.status else "Active"
        age = _format_age(ns.metadata.creation_timestamp)
        lines.append(f"{name:<24} {phase:<9} {age}")
    return "\n".join(lines)


@mcp.tool()
def list_pods(namespace: str = "default") -> str:
    """List Kubernetes Pods in a namespace (or pass 'all' to list pods across all namespaces).

    Args:
        namespace: Target Kubernetes namespace (default: 'default', or 'all' for all namespaces).

    Returns:
        Formatted table of pods including READY count, STATUS/reason, RESTARTS, AGE, and NODE.
    """
    core_v1, _ = _load_k8s_clients()
    clean_ns = (namespace or "default").strip()
    if clean_ns.lower() in ("all", "*", "all-namespaces"):
        pods = core_v1.list_pod_for_all_namespaces().items
        lines = ["NAMESPACE         NAME                                              READY   STATUS             RESTARTS   AGE    NODE"]
        for p in pods:
            ns_name = p.metadata.namespace
            name = p.metadata.name
            c_statuses = p.status.container_statuses or [] if p.status else []
            total_c = len(p.spec.containers or [])
            ready_c = sum(1 for cs in c_statuses if cs.ready)
            restarts = sum(cs.restart_count or 0 for cs in c_statuses)
            status_str = p.status.phase if p.status else "Unknown"
            for cs in c_statuses:
                if cs.state and cs.state.waiting and cs.state.waiting.reason:
                    status_str = cs.state.waiting.reason
                    break
                if cs.state and cs.state.terminated and cs.state.terminated.reason:
                    status_str = cs.state.terminated.reason
                    break
            age = _format_age(p.metadata.creation_timestamp)
            node = p.spec.node_name or "<none>"
            lines.append(
                f"{ns_name:<17} {name:<49} {ready_c}/{total_c:<5} {status_str:<18} {restarts:<10} {age:<6} {node}"
            )
        return "\n".join(lines)

    pods = core_v1.list_namespaced_pod(namespace=clean_ns).items
    if not pods:
        return f"No pods found in namespace '{clean_ns}'."
    lines = ["NAME                                              READY   STATUS             RESTARTS   AGE    NODE"]
    for p in pods:
        name = p.metadata.name
        c_statuses = p.status.container_statuses or [] if p.status else []
        total_c = len(p.spec.containers or [])
        ready_c = sum(1 for cs in c_statuses if cs.ready)
        restarts = sum(cs.restart_count or 0 for cs in c_statuses)
        status_str = p.status.phase if p.status else "Unknown"
        for cs in c_statuses:
            if cs.state and cs.state.waiting and cs.state.waiting.reason:
                status_str = cs.state.waiting.reason
                break
            if cs.state and cs.state.terminated and cs.state.terminated.reason:
                status_str = cs.state.terminated.reason
                break
        age = _format_age(p.metadata.creation_timestamp)
        node = p.spec.node_name or "<none>"
        lines.append(
            f"{name:<49} {ready_c}/{total_c:<5} {status_str:<18} {restarts:<10} {age:<6} {node}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: str = "",
    previous: bool = False,
    tail_lines: int = 200,
) -> str:
    """Fetch diagnostic pod description, container states, events, and container logs for a Kubernetes Pod.

    Args:
        pod_name: The name (or deployment prefix) of the Kubernetes Pod to inspect.
        namespace: The Kubernetes namespace where the pod is located (default: 'default').
        container: Optional container name within the pod (leave empty for default container).
        previous: Whether to fetch logs from a previous terminated container instance.
        tail_lines: Number of most recent log lines to fetch (default: 200).

    Returns:
        Combined pod description (status, exit codes, resource limits, events) and container logs.
    """
    from kubernetes.client.exceptions import ApiException

    clean_pod, clean_ns = _normalize_target(pod_name, namespace)
    core_v1, _ = _load_k8s_clients()
    resolved_pod = _resolve_pod_name(core_v1, clean_pod, clean_ns)

    sections: List[str] = []
    errors: List[str] = []
    describe_text = ""

    try:
        pod_obj = core_v1.read_namespaced_pod(name=resolved_pod, namespace=clean_ns)
        ev_list = core_v1.list_namespaced_event(
            namespace=clean_ns,
            field_selector=f"involvedObject.name={resolved_pod}",
        ).items
        describe_text = _format_pod_describe(pod_obj, ev_list)
        sections.append(describe_text)
    except ApiException as exc:
        errors.append(f"Failed to read pod '{resolved_pod}' in namespace '{clean_ns}': {exc.reason} ({exc.status})")

    log_kwargs: Dict[str, Any] = {
        "name": resolved_pod,
        "namespace": clean_ns,
        "tail_lines": tail_lines if tail_lines and tail_lines > 0 else 200,
        "previous": bool(previous),
    }
    if container and container.strip():
        log_kwargs["container"] = container.strip()

    try:
        current_logs = core_v1.read_namespaced_pod_log(**log_kwargs)
        if current_logs and current_logs.strip():
            sections.append(current_logs.strip())
    except ApiException as exc:
        errors.append(f"Log read note ({'previous' if previous else 'current'}): {exc.reason} - {exc.body}")

    # Also check previous terminated container logs if container restarted or current logs were empty
    if not previous and ("Restart Count:" in describe_text or "BackOff" in describe_text or len(sections) <= 1):
        try:
            prev_kwargs = dict(log_kwargs, previous=True)
            prev_logs = core_v1.read_namespaced_pod_log(**prev_kwargs)
            if prev_logs and prev_logs.strip() and prev_logs.strip() not in sections:
                sections.append(prev_logs.strip())
        except Exception:
            pass

    if not sections:
        err_msg = "; ".join(errors) if errors else "No pod data or logs found."
        return f"Error fetching logs for pod '{clean_pod}' in namespace '{clean_ns}': {err_msg}"

    return "\n".join(sections)


@mcp.tool()
def get_pod_events(
    pod_name: str = "",
    namespace: str = "default",
) -> str:
    """Fetch Kubernetes events for a specific Pod (or all events in the namespace if pod_name is empty).

    Args:
        pod_name: The name of the Kubernetes Pod to fetch events for (or empty/'all' for namespace events).
        namespace: The Kubernetes namespace (default: 'default').

    Returns:
        Formatted table of Kubernetes events with LAST SEEN, TYPE, REASON, OBJECT, and MESSAGE.
    """
    core_v1, _ = _load_k8s_clients()
    clean_ns = (namespace or "default").strip() or "default"

    if pod_name and pod_name.strip() and pod_name.strip().lower() not in ("all", "*"):
        clean_pod, clean_ns = _normalize_target(pod_name, clean_ns)
        resolved_pod = _resolve_pod_name(core_v1, clean_pod, clean_ns)
        events = core_v1.list_namespaced_event(
            namespace=clean_ns,
            field_selector=f"involvedObject.name={resolved_pod}",
        ).items
        if not events:
            # Also include events matching prefix (e.g. Deployment + ReplicaSet + Pod events)
            all_events = core_v1.list_namespaced_event(namespace=clean_ns).items
            events = [
                ev
                for ev in all_events
                if ev.involved_object
                and ev.involved_object.name
                and (
                    ev.involved_object.name == clean_pod
                    or ev.involved_object.name == resolved_pod
                    or ev.involved_object.name.startswith(f"{clean_pod}-")
                )
            ]
    else:
        events = core_v1.list_namespaced_event(namespace=clean_ns).items

    if not events:
        target_label = f"pod '{pod_name}' in " if pod_name else ""
        return f"No events found for {target_label}namespace '{clean_ns}'."

    lines = ["LAST SEEN   TYPE      REASON              OBJECT                          MESSAGE"]
    for ev in events:
        ev_ts = ev.last_timestamp or ev.event_time or (ev.metadata.creation_timestamp if ev.metadata else None)
        age = _format_age(ev_ts)
        ev_type = ev.type or "Normal"
        reason = ev.reason or ""
        obj_kind = (ev.involved_object.kind or "pod").lower() if ev.involved_object else "pod"
        obj_name = (ev.involved_object.name or "") if ev.involved_object else ""
        obj_ref = f"{obj_kind}/{obj_name}"
        msg = (ev.message or "").replace("\n", " ")
        lines.append(f"{age:<11} {ev_type:<9} {reason:<19} {obj_ref:<31} {msg}")
    return "\n".join(lines)


@mcp.tool()
def get_deployment_history(
    deployment_name: str,
    namespace: str = "default",
) -> str:
    """Fetch the rollout and revision history of a Kubernetes Deployment (or parent Deployment of a Pod).

    Args:
        deployment_name: The name of the Kubernetes Deployment or Pod to inspect.
        namespace: The Kubernetes namespace where the workload is located (default: 'default').

    Returns:
        Deployment rollout history and per-revision Pod Template image and resource configuration.
    """
    from kubernetes.client.exceptions import ApiException

    clean_target, clean_ns = _normalize_target(deployment_name, namespace)
    core_v1, apps_v1 = _load_k8s_clients()

    candidates: List[str] = [clean_target]
    pod_hash_match = re.match(
        r"^([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)-[a-z0-9]{5,10}-[a-z0-9]{4,6}$",
        clean_target,
        re.IGNORECASE,
    )
    if pod_hash_match and pod_hash_match.group(1) not in candidates:
        candidates.append(pod_hash_match.group(1))

    deploy_obj = None
    resolved_deploy_name = clean_target
    for cand in candidates:
        try:
            deploy_obj = apps_v1.read_namespaced_deployment(name=cand, namespace=clean_ns)
            resolved_deploy_name = cand
            break
        except ApiException:
            continue

    if deploy_obj is not None:
        all_rs = apps_v1.list_namespaced_replica_set(namespace=clean_ns).items
        owned_rs = []
        for rs in all_rs:
            owners = rs.metadata.owner_references or []
            if any(o.kind == "Deployment" and o.name == resolved_deploy_name for o in owners):
                rev_str = (rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0")
                try:
                    rev_num = int(rev_str)
                except ValueError:
                    rev_num = 0
                owned_rs.append((rev_num, rs))

        owned_rs.sort(key=lambda item: item[0])
        lines = [
            f"deployment.apps/{resolved_deploy_name}",
            "REVISION  CHANGE-CAUSE",
        ]
        for rev_num, rs in owned_rs:
            cause = (rs.metadata.annotations or {}).get("kubernetes.io/change-cause") or "<none>"
            lines.append(f"{rev_num:<9} {cause}")

        for rev_num, rs in owned_rs[-3:]:
            lines.append(f"deployment.apps/{resolved_deploy_name} with revision #{rev_num}")
            lines.append("Pod Template:")
            lines.append("  Containers:")
            for c in (rs.spec.template.spec.containers if rs.spec and rs.spec.template and rs.spec.template.spec else []):
                lines.append(f"   {c.name}:")
                lines.append(f"    Image:      {c.image}")
                if c.resources and c.resources.limits:
                    lines.append(f"    Limits:     {dict(c.resources.limits)}")
                if c.resources and c.resources.requests:
                    lines.append(f"    Requests:   {dict(c.resources.requests)}")

        return "\n".join(lines)

    # Fallback: standalone Pod description
    try:
        resolved_pod = _resolve_pod_name(core_v1, clean_target, clean_ns)
        pod_obj = core_v1.read_namespaced_pod(name=resolved_pod, namespace=clean_ns)
        ev_list = core_v1.list_namespaced_event(
            namespace=clean_ns,
            field_selector=f"involvedObject.name={resolved_pod}",
        ).items
        return _format_pod_describe(pod_obj, ev_list)
    except Exception as exc:
        return f"Could not find deployment or pod '{clean_target}' in namespace '{clean_ns}': {exc}"


@mcp.tool()
def get_nodes_info(node_name: str = "") -> str:
    """Fetch Kubernetes cluster node status, health conditions (Ready, MemoryPressure, DiskPressure, PIDPressure), capacity, allocatable resources, and taints.

    Args:
        node_name: Optional specific node name to inspect (leave empty to inspect all cluster nodes).

    Returns:
        Detailed node health, conditions, capacity, and allocatable resource summary.
    """
    core_v1, _ = _load_k8s_clients()
    if node_name and node_name.strip() and node_name.strip().lower() not in ("all", "*"):
        clean_node, _ = _normalize_target(node_name)
        nodes = [core_v1.read_node(name=clean_node)]
    else:
        nodes = core_v1.list_node().items

    if not nodes:
        return "No nodes found in the cluster."

    sections: List[str] = []
    for n in nodes:
        name = n.metadata.name
        labels = n.metadata.labels or {}
        conditions = n.status.conditions or [] if n.status else []
        ready_cond = next((c.status for c in conditions if c.type == "Ready"), "Unknown")
        status_str = "Ready" if ready_cond == "True" else f"NotReady({ready_cond})"
        age = _format_age(n.metadata.creation_timestamp)
        kubelet_ver = n.status.node_info.kubelet_version if n.status and n.status.node_info else ""
        os_image = n.status.node_info.os_image if n.status and n.status.node_info else ""
        instance_type = labels.get("node.kubernetes.io/instance-type", "<unknown>")
        zone = labels.get("topology.kubernetes.io/zone", "<unknown>")

        lines = [
            f"Node: {name}",
            f"  Status:         {status_str}",
            f"  Age:            {age}",
            f"  Version:        {kubelet_ver}",
            f"  Instance Type:  {instance_type} (zone: {zone})",
            f"  OS Image:       {os_image}",
        ]

        if n.spec and n.spec.taints:
            taint_strs = [f"{t.key}={t.value or ''}:{t.effect}" for t in n.spec.taints]
            lines.append(f"  Taints:         {', '.join(taint_strs)}")
        else:
            lines.append("  Taints:         <none>")

        if n.status and n.status.capacity and n.status.allocatable:
            cap = n.status.capacity
            alloc = n.status.allocatable
            lines.append(
                f"  Capacity:       cpu={cap.get('cpu')}, memory={cap.get('memory')}, pods={cap.get('pods')}, ephemeral-storage={cap.get('ephemeral-storage')}"
            )
            lines.append(
                f"  Allocatable:    cpu={alloc.get('cpu')}, memory={alloc.get('memory')}, pods={alloc.get('pods')}, ephemeral-storage={alloc.get('ephemeral-storage')}"
            )

        if conditions:
            lines.append("  Conditions:")
            for c in conditions:
                lines.append(f"    - {c.type}: {c.status} (Reason: {c.reason or 'n/a'}) - {c.message or ''}")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


@mcp.tool()
def get_cluster_resources(namespace: str = "default") -> str:
    """Inspect Deployments, Services, Endpoints, and unhealthy Pods in a Kubernetes namespace (or 'all' namespaces).

    Args:
        namespace: Target Kubernetes namespace (default: 'default', or 'all' for all namespaces).

    Returns:
        Summary of Deployments, Services, Endpoints, and any unhealthy Pods.
    """
    core_v1, apps_v1 = _load_k8s_clients()
    clean_ns = (namespace or "default").strip() or "default"
    all_ns = clean_ns.lower() in ("all", "*", "all-namespaces")

    deployments = (
        apps_v1.list_deployment_for_all_namespaces().items
        if all_ns
        else apps_v1.list_namespaced_deployment(namespace=clean_ns).items
    )
    services = (
        core_v1.list_service_for_all_namespaces().items
        if all_ns
        else core_v1.list_namespaced_service(namespace=clean_ns).items
    )
    endpoints = (
        core_v1.list_endpoints_for_all_namespaces().items
        if all_ns
        else core_v1.list_namespaced_endpoints(namespace=clean_ns).items
    )

    ep_map: Dict[Tuple[str, str], int] = {}
    for ep in endpoints:
        count = 0
        for sub in ep.subsets or []:
            count += len(sub.addresses or [])
        ep_map[(ep.metadata.namespace, ep.metadata.name)] = count

    lines = [f"=== Deployments ({'all namespaces' if all_ns else clean_ns}) ==="]
    if not deployments:
        lines.append("  <none>")
    for d in deployments:
        ready = d.status.ready_replicas or 0 if d.status else 0
        desired = d.spec.replicas or 0 if d.spec else 0
        avail = d.status.available_replicas or 0 if d.status else 0
        lines.append(f"  {d.metadata.namespace}/{d.metadata.name}: ready={ready}/{desired}, available={avail}")

    lines.append(f"\n=== Services & Active Endpoints ({'all namespaces' if all_ns else clean_ns}) ===")
    if not services:
        lines.append("  <none>")
    for s in services:
        svc_type = s.spec.type if s.spec else "ClusterIP"
        cluster_ip = s.spec.cluster_ip if s.spec else "<none>"
        ext_ips = [ing.ip or ing.hostname for ing in (s.status.load_balancer.ingress or [])] if (s.status and s.status.load_balancer) else []
        ext_str = ",".join(filter(None, ext_ips)) or "<none>"
        ep_count = ep_map.get((s.metadata.namespace, s.metadata.name), 0)
        ports = ",".join(f"{p.port}:{p.target_port}/{p.protocol}" for p in (s.spec.ports or [])) if s.spec else ""
        lines.append(
            f"  {s.metadata.namespace}/{s.metadata.name}: type={svc_type}, clusterIP={cluster_ip}, externalIP={ext_str}, ports=[{ports}], readyEndpoints={ep_count}"
        )

    return "\n".join(lines)


def create_mcp_starlette_app() -> Any:
    """Creates the ASGI Starlette application serving MCP over Streamable HTTP at `/mcp` and health probe at `/healthz`."""
    kwargs: Dict[str, Any] = {
        "streamable_http_path": "/mcp",
        "stateless_http": True,
        "host": "0.0.0.0",
    }
    if TransportSecuritySettings is not None:
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
    return mcp.streamable_http_app(**kwargs)


app = create_mcp_starlette_app()


def main() -> None:
    """Entrypoint for running the Kubernetes MCP Server."""
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
