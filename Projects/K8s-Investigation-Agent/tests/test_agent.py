"""
Tests for high-level Kubernetes Investigation Agent interface.
"""

from pathlib import Path
from k8s_investigate.agent import KubernetesInvestigationAgent
from k8s_investigate.models import FailureCategory


def test_agent_investigate_string():
    agent = KubernetesInvestigationAgent()
    log = "2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Exit code 137."
    report = agent.investigate(log)

    assert report.total_log_lines == 1
    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.OOM_KILL


def test_agent_investigate_sample_file():
    agent = KubernetesInvestigationAgent()
    sample_file = Path("sample_logs/oom_killed_crashloop.log")
    report = agent.investigate(sample_file)

    assert report.total_log_lines > 5
    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.OOM_KILL
    assert len(report.findings) >= 2  # OOM and CrashLoop
    assert len(report.remediations) >= 2


def test_agent_markdown_and_json_serialization():
    agent = KubernetesInvestigationAgent()
    log = "2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi."
    report = agent.investigate(log)

    md = agent.renderer.render_markdown(report)
    assert "# 🛡️ Kubernetes Incident Investigation Report" in md
    assert "Primary Root Cause" in md

    js = agent.renderer.render_json(report)
    assert "investigation_id" in js
    assert "root_cause" in js


def test_agent_utf16_and_prompt_path(tmp_path):
    agent = KubernetesInvestigationAgent()
    log_file = tmp_path / "powershell_describe.log"
    content = (
        "Name:             nginx\n"
        "Namespace:        default\n"
        "Node:             minikube/192.168.49.2\n"
        "Containers:\n"
        "  nginx:\n"
        "    Image:          nginx:1.32.7\n"
        "    State:          Waiting\n"
        "      Reason:       ErrImagePull\n"
        "Events:\n"
        "  Warning  Failed          23s (x4 over 116s)     kubelet  Failed to pull image \"nginx:1.32.7\": rpc error: code = NotFound desc = failed to pull and unpack image \"docker.io/library/nginx:1.32.7\": not found\n"
        "  Normal   SandboxChanged  2m                     kubelet  Pod sandbox changed, it will be killed and re-created.\n"
    )
    log_file.write_bytes(content.encode("utf-16"))

    prompt = f"Investigate the pod failure from the attached log file {log_file}"
    report = agent.investigate(prompt)

    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.IMAGE_PULL_FAILURE
    assert report.blast_radius.pods_affected == ["nginx"]

