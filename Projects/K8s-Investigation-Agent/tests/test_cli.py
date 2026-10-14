"""
Tests for CLI commands using get_pod_logs tool.
"""

from unittest.mock import patch
from click.testing import CliRunner
from k8s_investigate.cli import main


SAMPLE_OOM_POD_LOGS = (
    "Name:             oom-test\n"
    "Namespace:        default\n"
    "Containers:\n"
    "  stress:\n"
    "    State:          Terminated\n"
    "      Reason:       OOMKilled\n"
    "      Exit Code:    1\n"
    "Events:\n"
    "  Warning  BackOff  12s (x5 over 91s)  kubelet  Back-off restarting failed container stress in pod oom-test_default\n"
    "stress: FAIL: [1] (415) <-- worker 8 got signal 9\n"
)


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Kubernetes Investigation Agent CLI" in result.output
    assert "--pod" in result.output


def test_cli_pod_run():
    runner = CliRunner()
    with patch("k8s_investigate.agent.get_pod_logs", return_value=SAMPLE_OOM_POD_LOGS) as mock_tool:
        result = runner.invoke(main, ["oom-test"])

    assert result.exit_code == 0
    mock_tool.assert_called_once_with(
        pod_name="oom-test",
        namespace="default",
        container=None,
        previous=False,
        tail_lines=None,
    )
    assert "OOM_KILL" in result.output or "OOMKilled" in result.output


def test_cli_export_json(tmp_path):
    runner = CliRunner()
    out_file = tmp_path / "out.json"

    with patch("k8s_investigate.agent.get_pod_logs", return_value=SAMPLE_OOM_POD_LOGS):
        result = runner.invoke(main, ["--pod", "oom-test", "--output", str(out_file), "--format", "json", "--quiet"])

    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert '"category": "OOM_KILL"' in content


def test_cli_export_markdown(tmp_path):
    runner = CliRunner()
    out_file = tmp_path / "out.md"

    with patch("k8s_investigate.agent.get_pod_logs", return_value=SAMPLE_OOM_POD_LOGS):
        result = runner.invoke(main, ["oom-test", "--output", str(out_file), "--format", "markdown", "--quiet"])

    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# 🛡️ Kubernetes Incident Investigation Report" in content


def test_cli_run_with_prompt():
    runner = CliRunner()
    nginx_logs = (
        "Name:             nginx\n"
        "Namespace:        default\n"
        "Containers:\n"
        "  nginx:\n"
        "    State:          Waiting\n"
        "      Reason:       ErrImagePull\n"
        "Events:\n"
        "  Warning  Failed  10s  kubelet  Failed to pull image \"nginx:1.32.7\": not found\n"
    )

    with patch("k8s_investigate.agent.get_pod_logs", return_value=nginx_logs) as mock_tool:
        result = runner.invoke(main, ["run", "Investigate the pod failure for pod nginx"])

    assert result.exit_code == 0
    mock_tool.assert_called_once_with(
        pod_name="nginx",
        namespace="default",
        container=None,
        previous=False,
        tail_lines=None,
    )
    assert "IMAGE_PULL_FAILURE" in result.output
