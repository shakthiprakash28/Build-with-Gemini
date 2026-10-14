"""
Kubernetes cluster tools for the Investigation Agent.
Provides `get_pod_logs`, `get_pod_events`, and `get_deployment_history` tools
to fetch container logs, pod diagnostic events, and deployment revision history
directly from a Kubernetes cluster via `kubectl`.
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Optional, Tuple


def _normalize_pod_and_namespace(pod_name: str, namespace: str = "default") -> Tuple[str, str]:
    """Normalizes resource name and namespace, supporting 'pod/<name>', 'deployment/<name>', or '<namespace>/<name>' notation."""
    if not pod_name or not pod_name.strip():
        raise ValueError("pod_name must be a non-empty string.")

    clean_pod = pod_name.strip().strip("\"'`")
    clean_ns = (namespace or "default").strip().strip("\"'`")

    if "/" in clean_pod:
        prefix, remainder = clean_pod.split("/", 1)
        if prefix.lower() in ("pod", "pods", "deployment", "deployments", "deploy", "deployment.apps", "replicaset", "rs"):
            clean_pod = remainder
        elif clean_ns == "default" and remainder:
            clean_ns = prefix
            clean_pod = remainder

    return clean_pod, clean_ns


def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: Optional[str] = None,
    previous: bool = False,
    tail_lines: Optional[int] = None,
    include_describe: bool = True,
) -> str:
    """
    Fetch the logs of a specific Kubernetes Pod using kubectl.

    Args:
        pod_name: The name of the Kubernetes Pod to fetch logs from.
        namespace: The Kubernetes namespace where the pod is located (default: "default").
        container: Optional specific container name within the pod.
        previous: Whether to fetch logs from a previous terminated container instance.
        tail_lines: Optional number of most recent log lines to fetch.
        include_describe: Whether to include pod status and event diagnostics from `kubectl describe pod`.

    Returns:
        Combined log output and pod diagnostic events for the specified Kubernetes Pod.
    """
    clean_pod, clean_ns = _normalize_pod_and_namespace(pod_name, namespace)

    collected_sections: List[str] = []
    errors: List[str] = []

    # 1. Fetch pod description & events if requested (provides container state, exit codes, limits, and K8s events)
    describe_output = ""
    if include_describe:
        describe_cmd = ["kubectl", "describe", "pod", clean_pod, "-n", clean_ns]
        try:
            desc_proc = subprocess.run(
                describe_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if desc_proc.returncode == 0 and desc_proc.stdout and desc_proc.stdout.strip():
                describe_output = desc_proc.stdout.strip()
                collected_sections.append(describe_output)
            elif desc_proc.stderr and desc_proc.stderr.strip():
                errors.append(desc_proc.stderr.strip())
        except FileNotFoundError as exc:
            raise RuntimeError(
                "kubectl command not found. Ensure kubectl is installed and available in PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            errors.append(f"Timed out running {' '.join(describe_cmd)}: {exc}")

    # 2. Fetch container stdout/stderr logs via `kubectl logs`
    logs_cmd = ["kubectl", "logs", clean_pod, "-n", clean_ns]
    if container:
        logs_cmd.extend(["-c", container])
    if previous:
        logs_cmd.append("--previous")
    if tail_lines is not None:
        logs_cmd.extend(["--tail", str(tail_lines)])

    logs_output = ""
    try:
        logs_proc = subprocess.run(
            logs_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        stdout_text = (logs_proc.stdout or "").strip()
        stderr_text = (logs_proc.stderr or "").strip()

        if stdout_text:
            logs_output = stdout_text
        if stderr_text:
            # Capture kubectl stderr (e.g. 'is waiting to start: trying and failing to pull image' or 'CrashLoopBackOff')
            if "not found" in stderr_text.lower() and logs_proc.returncode != 0 and not stdout_text:
                errors.append(stderr_text)
            else:
                logs_output = f"{logs_output}\n{stderr_text}".strip() if logs_output else stderr_text

        if logs_output and logs_output != describe_output:
            collected_sections.append(logs_output)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kubectl command not found. Ensure kubectl is installed and available in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        errors.append(f"Timed out running {' '.join(logs_cmd)}: {exc}")

    # 3. If not explicitly requesting --previous, also check --previous if container restarted or current logs failed
    if not previous and (not logs_output or "Restart Count:" in describe_output or "BackOff" in describe_output):
        prev_cmd = ["kubectl", "logs", clean_pod, "-n", clean_ns, "--previous"]
        if container:
            prev_cmd.extend(["-c", container])
        if tail_lines is not None:
            prev_cmd.extend(["--tail", str(tail_lines)])
        try:
            prev_proc = subprocess.run(
                prev_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            prev_stdout = (prev_proc.stdout or "").strip()
            if prev_proc.returncode == 0 and prev_stdout and prev_stdout not in collected_sections:
                collected_sections.append(prev_stdout)
        except Exception:
            pass

    if not collected_sections:
        err_detail = "; ".join(dict.fromkeys(errors)) if errors else "No logs returned from cluster."
        raise RuntimeError(
            f"Failed to fetch logs for pod '{clean_pod}' in namespace '{clean_ns}': {err_detail}"
        )

    return "\n".join(collected_sections)


def get_pod_events(
    pod_name: str,
    namespace: str = "default",
) -> str:
    """
    Fetch the events of a specific Kubernetes Pod using kubectl.

    Args:
        pod_name: The name of the Kubernetes Pod to fetch events for.
        namespace: The Kubernetes namespace where the pod is located (default: "default").

    Returns:
        Kubernetes events output for the specified Pod.
    """
    clean_pod, clean_ns = _normalize_pod_and_namespace(pod_name, namespace)

    events_cmd = [
        "kubectl",
        "get",
        "events",
        "--field-selector",
        f"involvedObject.name={clean_pod}",
        "-n",
        clean_ns,
    ]

    errors: List[str] = []
    try:
        events_proc = subprocess.run(
            events_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        stdout_text = (events_proc.stdout or "").strip()
        stderr_text = (events_proc.stderr or "").strip()

        if events_proc.returncode == 0 and stdout_text and not stdout_text.lower().startswith("no resources found"):
            return stdout_text

        if stderr_text:
            errors.append(stderr_text)
        elif stdout_text:
            errors.append(stdout_text)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kubectl command not found. Ensure kubectl is installed and available in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        errors.append(f"Timed out running {' '.join(events_cmd)}: {exc}")

    # Fallback: check `kubectl describe pod` if `kubectl get events` had no active resources
    describe_cmd = ["kubectl", "describe", "pod", clean_pod, "-n", clean_ns]
    try:
        desc_proc = subprocess.run(
            describe_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        desc_stdout = (desc_proc.stdout or "").strip()
        desc_stderr = (desc_proc.stderr or "").strip()
        if desc_proc.returncode == 0 and desc_stdout:
            return desc_stdout
        if desc_stderr:
            errors.append(desc_stderr)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kubectl command not found. Ensure kubectl is installed and available in PATH."
        ) from exc
    except Exception:
        pass

    err_detail = "; ".join(dict.fromkeys(errors)) if errors else "No events returned from cluster."
    raise RuntimeError(
        f"Failed to fetch events for pod '{clean_pod}' in namespace '{clean_ns}': {err_detail}"
    )


def get_deployment_history(
    deployment_name: str = "",
    namespace: str = "default",
    revision: Optional[int] = None,
    pod_name: Optional[str] = None,
) -> str:
    """
    Fetch the rollout and revision history of a Kubernetes Deployment (or Pod) using kubectl
    to analyze any recent changes in the pod version or container image.

    Args:
        deployment_name: The name of the Kubernetes Deployment (or Pod) to inspect.
        namespace: The Kubernetes namespace where the workload is located (default: "default").
        revision: Optional specific revision number to inspect in detail.
        pod_name: Optional pod name if called with a Pod identifier instead of deployment_name.

    Returns:
        Deployment rollout history and revision/version details for the specified workload.
    """
    target = (deployment_name or pod_name or "").strip()
    if not target:
        raise ValueError("deployment_name or pod_name must be a non-empty string.")

    clean_target, clean_ns = _normalize_pod_and_namespace(target, namespace)

    # Build candidate deployment names (if a pod name like '<deploy>-<rs-hash>-<pod-hash>' was passed)
    candidates: List[str] = [clean_target]
    pod_hash_match = re.match(
        r"^([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)-[a-z0-9]{5,10}-[a-z0-9]{4,6}$",
        clean_target,
        re.IGNORECASE,
    )
    if pod_hash_match and pod_hash_match.group(1) not in candidates:
        candidates.append(pod_hash_match.group(1))

    errors: List[str] = []

    for cand_deploy in candidates:
        history_cmd = ["kubectl", "rollout", "history", f"deployment/{cand_deploy}", "-n", clean_ns]
        if revision is not None:
            history_cmd.append(f"--revision={revision}")

        try:
            hist_proc = subprocess.run(
                history_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            stdout_text = (hist_proc.stdout or "").strip()
            stderr_text = (hist_proc.stderr or "").strip()

            if hist_proc.returncode == 0 and stdout_text:
                collected_sections = [stdout_text]

                # If no specific revision was requested and CHANGE-CAUSE is '<none>',
                # inspect the recent revisions to compare Pod Template images across versions.
                if revision is None and "<none>" in stdout_text.lower() and "image:" not in stdout_text.lower():
                    revs = re.findall(r"^\s*(\d+)\s+", stdout_text, re.MULTILINE)
                    for rev in revs[-2:]:
                        rev_cmd = [
                            "kubectl",
                            "rollout",
                            "history",
                            f"deployment/{cand_deploy}",
                            f"--revision={rev}",
                            "-n",
                            clean_ns,
                        ]
                        try:
                            rev_proc = subprocess.run(
                                rev_cmd,
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=30,
                            )
                            rev_stdout = (rev_proc.stdout or "").strip()
                            if rev_proc.returncode == 0 and rev_stdout and rev_stdout not in collected_sections:
                                collected_sections.append(rev_stdout)
                        except Exception:
                            pass

                return "\n".join(collected_sections)

            if stderr_text:
                errors.append(stderr_text)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "kubectl command not found. Ensure kubectl is installed and available in PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            errors.append(f"Timed out running {' '.join(history_cmd)}: {exc}")

    # Fallback for standalone Pods not managed by a Deployment: inspect Pod image & version metadata via describe
    describe_cmd = ["kubectl", "describe", "pod", clean_target, "-n", clean_ns]
    try:
        desc_proc = subprocess.run(
            describe_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        desc_stdout = (desc_proc.stdout or "").strip()
        desc_stderr = (desc_proc.stderr or "").strip()
        if desc_proc.returncode == 0 and desc_stdout:
            return desc_stdout
        if desc_stderr:
            errors.append(desc_stderr)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kubectl command not found. Ensure kubectl is installed and available in PATH."
        ) from exc
    except Exception:
        pass

    err_detail = "; ".join(dict.fromkeys(errors)) if errors else "No deployment history returned from cluster."
    raise RuntimeError(
        f"Failed to fetch deployment history for '{clean_target}' in namespace '{clean_ns}': {err_detail}"
    )


