"""Automated evaluation benchmark tests for the 10 synthesized Kubernetes incident test cases."""

import json
from pathlib import Path

import pytest

from k8s_investigate.engine import InvestigationEngine
from k8s_investigate.parser import LogParser

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval_dataset"
MANIFEST_PATH = EVAL_DIR / "eval_cases.json"


def load_eval_cases():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.mark.parametrize("case", load_eval_cases(), ids=lambda c: f"{c['id']}_{c['slug']}")
def test_synthesized_k8s_incident_eval_case(case):
    """Verifies that InvestigationEngine accurately diagnoses each of the 10 benchmark cases."""
    log_path = EVAL_DIR / case["log_file"]
    assert log_path.exists(), f"Missing log file for {case['id']}: {log_path}"

    raw_text = log_path.read_text(encoding="utf-8")
    parser = LogParser()
    entries = parser.parse_text(raw_text)
    engine = InvestigationEngine()
    report = engine.analyze(entries)

    # 1. Verify root cause category and severity
    assert report.root_cause is not None, f"Expected root cause for {case['id']}"
    assert report.root_cause.category.value == case["expected_root_cause_category"], (
        f"Root cause mismatch for {case['id']}: got {report.root_cause.category.value}, "
        f"expected {case['expected_root_cause_category']}"
    )
    assert report.root_cause.severity.value == case["expected_severity"], (
        f"Severity mismatch for {case['id']}: got {report.root_cause.severity.value}, "
        f"expected {case['expected_severity']}"
    )

    # 2. Verify subtype metadata when specified
    expected_subtype = case.get("expected_subtype")
    if expected_subtype:
        primary_finding = next(
            (f for f in report.findings if f.id == report.root_cause.primary_finding_id),
            report.findings[0],
        )
        actual_subtype = primary_finding.metadata.get("subtype") or primary_finding.metadata.get("network_subsystem")
        assert actual_subtype == expected_subtype, (
            f"Subtype mismatch for {case['id']}: got {actual_subtype}, expected {expected_subtype}"
        )

    # 3. Verify blast radius accuracy
    for expected_pod in case["expected_impacted_resources"]:
        assert expected_pod in report.blast_radius.pods_affected
    assert case["expected_namespace"] in report.blast_radius.namespaces_affected
    assert case["expected_container"] in report.blast_radius.containers_affected

    # 4. Verify remediation commands
    generated_cmds = [r.kubectl_command for r in report.remediations if r.kubectl_command]
    for expected_cmd in case["expected_remediation_commands"]:
        assert expected_cmd in generated_cmds, (
            f"Missing remediation command '{expected_cmd}' in {generated_cmds} for {case['id']}"
        )


def test_agent_execution_traces_bundle():
    """Verifies that all 10 agent execution trace files and summary artifacts are generated and pass ground-truth checks."""
    traces_dir = EVAL_DIR / "traces"
    summary_path = traces_dir / "trace_summary.json"
    jsonl_path = traces_dir / "eval_traces.jsonl"
    report_md_path = traces_dir / "TRACE_REPORT.md"

    assert summary_path.exists(), "Missing eval_dataset/traces/trace_summary.json"
    assert jsonl_path.exists(), "Missing eval_dataset/traces/eval_traces.jsonl"
    assert report_md_path.exists(), "Missing eval_dataset/traces/TRACE_REPORT.md"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_cases"] == 10
    assert summary["passed_cases"] == 10
    assert summary["accuracy_rate"] == 1.0
    assert summary["total_tool_calls"] == 30
    assert summary["total_trace_steps"] == 90

    jsonl_lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(jsonl_lines) == 10

    for case_summary in summary["cases"]:
        trace_file = EVAL_DIR / case_summary["trace_file"]
        assert trace_file.exists(), f"Missing per-case trace file: {trace_file}"
        trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
        assert trace_data["evaluation"]["passed"] is True
        assert trace_data["evaluation"]["score"] == 1.0
        assert len(trace_data["trace_steps"]) == 9
        assert trace_data["execution_metrics"]["tools_invoked"] == [
            "get_pod_logs",
            "get_pod_events",
            "get_deployment_history",
        ]


def test_trace_grading_scorecard():
    """Verifies that the 6-dimension trace grading scorecard is generated and achieves 1000/1000 (A+)."""
    traces_dir = EVAL_DIR / "traces"
    scorecard_json = traces_dir / "scorecard.json"
    scorecard_md = traces_dir / "SCORECARD.md"

    assert scorecard_json.exists(), "Missing eval_dataset/traces/scorecard.json"
    assert scorecard_md.exists(), "Missing eval_dataset/traces/SCORECARD.md"

    data = json.loads(scorecard_json.read_text(encoding="utf-8"))
    summary = data["overall_summary"]
    assert summary["total_cases"] == 10
    assert summary["passed_cases"] == 10
    assert summary["total_points_earned"] == 1000.0
    assert summary["total_points_possible"] == 1000.0
    assert summary["overall_score_pct"] == 100.0
    assert summary["overall_grade"] == "A+"


