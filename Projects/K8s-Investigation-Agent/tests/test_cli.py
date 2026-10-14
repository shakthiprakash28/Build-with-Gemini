"""
Tests for CLI commands.
"""

from click.testing import CliRunner
from k8s_investigate.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Kubernetes Investigation Agent CLI" in result.output


def test_cli_file_run(tmp_path):
    runner = CliRunner()
    log_file = tmp_path / "test.log"
    log_file.write_text("2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi. Exit code 137.")

    result = runner.invoke(main, [str(log_file)])
    assert result.exit_code == 0
    assert "OOM_KILL" in result.output or "OOMKilled" in result.output


def test_cli_export_json(tmp_path):
    runner = CliRunner()
    log_file = tmp_path / "test.log"
    log_file.write_text("2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi.")
    out_file = tmp_path / "out.json"

    result = runner.invoke(main, [str(log_file), "--output", str(out_file), "--format", "json", "--quiet"])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert '"category": "OOM_KILL"' in content


def test_cli_export_markdown(tmp_path):
    runner = CliRunner()
    log_file = tmp_path / "test.log"
    log_file.write_text("2026-10-10T00:10:00Z stderr F Warning OOMKilled Pod memory limit exceeded: 512Mi.")
    out_file = tmp_path / "out.md"

    result = runner.invoke(main, [str(log_file), "--output", str(out_file), "--format", "markdown", "--quiet"])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# 🛡️ Kubernetes Incident Investigation Report" in content


def test_cli_run_with_prompt(tmp_path):
    runner = CliRunner()
    log_file = tmp_path / "nginx.log"
    log_file.write_bytes(
        (
            "Name:             nginx\n"
            "Namespace:        default\n"
            "Containers:\n"
            "  nginx:\n"
            "    State:          Waiting\n"
            "      Reason:       ErrImagePull\n"
            "Events:\n"
            "  Warning  Failed  10s  kubelet  Failed to pull image \"nginx:1.32.7\": not found\n"
        ).encode("utf-16")
    )

    result = runner.invoke(main, ["run", f"Investigate the pod failure from the attached log file {log_file}"])
    assert result.exit_code == 0
    assert "IMAGE_PULL_FAILURE" in result.output

