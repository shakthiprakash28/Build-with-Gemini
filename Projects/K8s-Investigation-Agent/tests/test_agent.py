"""
Tests for high-level Kubernetes Investigation Agent interface, get_pod_logs, get_pod_events, and get_deployment_history tools.
"""

from subprocess import CompletedProcess
from unittest.mock import patch

from k8s_investigate.agent import KubernetesInvestigationAgent, analyze_kubernetes_logs
from k8s_investigate.models import FailureCategory
from k8s_investigate.tools import get_deployment_history, get_pod_events, get_pod_logs


def test_get_pod_logs_tool():
    sample_describe = (
        "Name:             oom-test\n"
        "Namespace:        default\n"
        "Containers:\n"
        "  stress:\n"
        "    State:          Terminated\n"
        "      Reason:       OOMKilled\n"
        "      Exit Code:    1\n"
    )
    sample_logs = (
        "stress: info: [1] dispatching hogs: 0 cpu, 0 io, 1 vm, 0 hdd\n"
        "stress: FAIL: [1] (415) <-- worker 8 got signal 9\n"
    )

    with patch("k8s_investigate.tools.subprocess.run") as mock_run:
        mock_run.side_effect = [
            CompletedProcess(args=["kubectl", "describe"], returncode=0, stdout=sample_describe, stderr=""),
            CompletedProcess(args=["kubectl", "logs"], returncode=0, stdout=sample_logs, stderr=""),
        ]
        output = get_pod_logs("oom-test", namespace="default")

    assert "Name:             oom-test" in output
    assert "Reason:       OOMKilled" in output
    assert "worker 8 got signal 9" in output


def test_get_pod_events_tool():
    sample_events = (
        "LAST SEEN   TYPE      REASON      OBJECT         MESSAGE\n"
        "85m         Normal    Scheduled   pod/oom-test   Successfully assigned default/oom-test to minikube\n"
        "3m57s       Warning   BackOff     pod/oom-test   Back-off restarting failed container stress in pod oom-test_default\n"
    )

    with patch("k8s_investigate.tools.subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(
            args=["kubectl", "get", "events"],
            returncode=0,
            stdout=sample_events,
            stderr="",
        )
        output = get_pod_events("oom-test", namespace="default")

    assert "LAST SEEN" in output
    assert "Back-off restarting failed container stress" in output
    mock_run.assert_called_once_with(
        ["kubectl", "get", "events", "--field-selector", "involvedObject.name=oom-test", "-n", "default"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def test_get_deployment_history_tool():
    sample_history = (
        "deployment.apps/payment-service \n"
        "REVISION  CHANGE-CAUSE\n"
        "1         <none>\n"
        "2         <none>\n"
    )
    sample_rev1 = (
        "deployment.apps/payment-service with revision #1\n"
        "Pod Template:\n"
        "  Containers:\n"
        "   payment:\n"
        "    Image:      payment-service:v1.2.0\n"
    )
    sample_rev2 = (
        "deployment.apps/payment-service with revision #2\n"
        "Pod Template:\n"
        "  Containers:\n"
        "   payment:\n"
        "    Image:      payment-service:v1.3.0-broken\n"
    )

    with patch("k8s_investigate.tools.subprocess.run") as mock_run:
        mock_run.side_effect = [
            # Pod name fails direct deployment lookup, then resolves to parent deployment 'payment-service'
            CompletedProcess(args=["kubectl", "rollout"], returncode=1, stdout="", stderr="Error from server (NotFound)"),
            CompletedProcess(args=["kubectl", "rollout"], returncode=0, stdout=sample_history, stderr=""),
            CompletedProcess(args=["kubectl", "rollout", "--revision=1"], returncode=0, stdout=sample_rev1, stderr=""),
            CompletedProcess(args=["kubectl", "rollout", "--revision=2"], returncode=0, stdout=sample_rev2, stderr=""),
        ]
        output = get_deployment_history("payment-service-7d84bf9bc-5k9lm", namespace="default")

    assert "deployment.apps/payment-service" in output
    assert "payment-service:v1.2.0" in output
    assert "payment-service:v1.3.0-broken" in output


def test_agent_investigate_pod_via_logs_events_and_deployment_history_tools():
    mock_log_output = (
        "stress: info: [1] dispatching hogs: 0 cpu, 0 io, 1 vm, 0 hdd\n"
        "stress: FAIL: [1] (415) <-- worker 8 got signal 9\n"
    )
    mock_events_output = (
        "LAST SEEN   TYPE      REASON      OBJECT         MESSAGE\n"
        "85m         Normal    Scheduled   pod/oom-test   Successfully assigned default/oom-test to minikube\n"
        "3m57s       Warning   BackOff     pod/oom-test   Back-off restarting failed container stress in pod oom-test_default\n"
    )
    mock_history_output = (
        "deployment.apps/oom-test \n"
        "REVISION  CHANGE-CAUSE\n"
        "1         <none>\n"
        "2         <none>\n"
        "deployment.apps/oom-test with revision #1\n"
        "Pod Template:\n"
        "  Containers:\n"
        "   stress:\n"
        "    Image:      polinux/stress:1.0.3\n"
        "deployment.apps/oom-test with revision #2\n"
        "Pod Template:\n"
        "  Containers:\n"
        "   stress:\n"
        "    Image:      polinux/stress:1.0.4\n"
    )

    agent = KubernetesInvestigationAgent(
        pod_log_tool=lambda **kwargs: mock_log_output,
        pod_event_tool=lambda **kwargs: mock_events_output,
        deployment_history_tool=lambda **kwargs: mock_history_output,
    )
    assert get_pod_logs in agent.tools
    assert get_pod_events in agent.tools
    assert get_deployment_history in agent.tools

    report = agent.investigate("oom-test")

    assert report.total_log_lines >= 4
    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.OOM_KILL
    assert any("polinux/stress:1.0.3" in cf and "polinux/stress:1.0.4" in cf for cf in report.root_cause.contributing_factors)
    assert any(rem.kubectl_command and "kubectl rollout undo deployment/oom-test" in rem.kubectl_command for rem in report.remediations)
    assert report.blast_radius.pods_affected == ["oom-test"]
    assert report.blast_radius.nodes_affected == ["minikube"]
    assert len(report.findings) >= 2  # OOM and CrashLoop
    assert len(report.remediations) >= 3


def test_agent_investigate_prompt_extracts_pod_and_uses_tool():
    called_args = {}

    def fake_get_pod_logs(pod_name: str, namespace: str = "default", **kwargs) -> str:
        called_args["pod_name"] = pod_name
        called_args["namespace"] = namespace
        return (
            "Name:             nginx\n"
            "Namespace:        default\n"
            "Node:             minikube/192.168.49.2\n"
            "Containers:\n"
            "  nginx:\n"
            "    Image:          nginx:1.32.7\n"
            "    State:          Waiting\n"
            "      Reason:       ErrImagePull\n"
            "Events:\n"
            "  Warning  Failed  23s (x4 over 116s)  kubelet  Failed to pull image \"nginx:1.32.7\": rpc error: code = NotFound desc = failed to pull and unpack image \"docker.io/library/nginx:1.32.7\": not found\n"
        )

    agent = KubernetesInvestigationAgent(pod_log_tool=fake_get_pod_logs)
    prompt = "Investigate the pod failure for pod nginx in default namespace"
    report = agent.investigate(prompt)

    assert called_args["pod_name"] == "nginx"
    assert called_args["namespace"] == "default"
    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.IMAGE_PULL_FAILURE
    assert report.blast_radius.pods_affected == ["nginx"]


def test_agent_investigate_string():
    agent = KubernetesInvestigationAgent()
    log = "2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Exit code 137."
    report = agent.investigate(log)

    assert report.total_log_lines == 1
    assert report.root_cause is not None
    assert report.root_cause.category == FailureCategory.OOM_KILL


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


def test_analyze_kubernetes_logs_adk_tool():
    log = "2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Exit code 137."
    md_report = analyze_kubernetes_logs(log)
    assert "# 🛡️ Kubernetes Incident Investigation Report" in md_report
    assert "OOM_KILL" in md_report or "OOM" in md_report
    assert "Primary Root Cause" in md_report


def test_adk_root_agent_configured_with_mcp_toolset():
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
    from k8s_investigate.agent import DEFAULT_K8S_MCP_SERVER_URL, root_agent

    mcp_toolsets = [t for t in root_agent.tools if isinstance(t, McpToolset)]
    assert len(mcp_toolsets) == 1
    conn_params = mcp_toolsets[0]._connection_params
    assert isinstance(conn_params, StreamableHTTPConnectionParams)
    assert conn_params.url == DEFAULT_K8S_MCP_SERVER_URL
    assert analyze_kubernetes_logs in root_agent.tools


def test_adk_root_agent_configured_with_memory_bank():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from google.adk.tools.preload_memory_tool import PreloadMemoryTool
    from k8s_investigate.agent import generate_memories_callback, root_agent
    from k8s_investigate.app_utils.memory_config import (
        KUBERNETES_INCIDENT_FINDINGS_TOPIC,
        KUBERNETES_REMEDIATIONS_TOPIC,
        memory_bank_config,
    )

    assert root_agent.after_agent_callback == generate_memories_callback
    assert any(isinstance(t, PreloadMemoryTool) for t in root_agent.tools)

    # Verify callback delegates to add_session_to_memory()
    mock_ctx = MagicMock()
    mock_ctx.add_session_to_memory = AsyncMock()
    asyncio.run(generate_memories_callback(mock_ctx))
    mock_ctx.add_session_to_memory.assert_awaited_once()

    # Verify callback is a safe no-op when memory_service is None
    mock_ctx_no_mem = MagicMock()
    mock_ctx_no_mem._invocation_context.memory_service = None
    mock_ctx_no_mem.add_session_to_memory = AsyncMock()
    asyncio.run(generate_memories_callback(mock_ctx_no_mem))
    mock_ctx_no_mem.add_session_to_memory.assert_not_awaited()

    # Verify memory_bank_config includes Kubernetes custom topics
    topics = memory_bank_config.customization_configs[0].memory_topics
    custom_labels = [
        t.custom_memory_topic.label
        for t in topics
        if t.custom_memory_topic is not None
    ]
    assert KUBERNETES_INCIDENT_FINDINGS_TOPIC.label in custom_labels
    assert KUBERNETES_REMEDIATIONS_TOPIC.label in custom_labels


def test_services_get_memory_service(monkeypatch):
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.memory.vertex_ai_memory_bank_service import (
        VertexAiMemoryBankService,
    )
    from k8s_investigate.app_utils import services

    services.get_memory_service.cache_clear()
    monkeypatch.delenv("MEMORY_SERVICE_URI", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", raising=False)
    mem_svc = services.get_memory_service()
    assert isinstance(mem_svc, InMemoryMemoryService)

    services.get_memory_service.cache_clear()
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "k8s-investigation-agent-511111")
    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "us-east1")
    monkeypatch.setenv(
        "GOOGLE_CLOUD_AGENT_ENGINE_ID",
        "projects/242122824215/locations/us-east1/reasoningEngines/818039949600227328",
    )
    vertex_mem_svc = services.get_memory_service()
    assert isinstance(vertex_mem_svc, VertexAiMemoryBankService)
    assert vertex_mem_svc._agent_engine_id == "818039949600227328"
    services.get_memory_service.cache_clear()



