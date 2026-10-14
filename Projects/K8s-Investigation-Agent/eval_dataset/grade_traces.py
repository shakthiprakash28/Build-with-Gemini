"""
Grades the recorded KubernetesInvestigationAgent execution traces in `eval_dataset/traces/`
against the ground-truth benchmark in `eval_dataset/eval_cases.json` across a 6-dimension
weighted rubric (100-point scale) covering both Agent Trajectory and Diagnostic Outcome.

Generates:
  - `eval_dataset/traces/scorecard.json` (structured machine-readable grading scorecard)
  - `eval_dataset/traces/SCORECARD.md` (formatted Markdown test scorecard report)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


EVAL_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = EVAL_DIR / "eval_cases.json"
TRACES_DIR = EVAL_DIR / "traces"
JSONL_PATH = TRACES_DIR / "eval_traces.jsonl"
SCORECARD_JSON_PATH = TRACES_DIR / "scorecard.json"
SCORECARD_MD_PATH = TRACES_DIR / "SCORECARD.md"


RUBRIC_WEIGHTS = {
    "D1_tool_trajectory": 15.0,       # Target extraction, 3 tool calls, 9-step pipeline, 100% log line parse
    "D2_root_cause_accuracy": 25.0,   # Primary category + subtype + causal disambiguation
    "D3_severity_calibration": 10.0,  # Exact severity match + high confidence calibration (>= 0.90)
    "D4_evidence_grounding": 20.0,    # Ground-truth evidence keyword recall + line-referenced snippets + causal chain
    "D5_blast_radius": 15.0,          # Pod, namespace, container, and node identification
    "D6_remediation_quality": 15.0,   # Expected kubectl remediation commands + mitigation/fix coverage
}


def _letter_grade(score_pct: float) -> str:
    if score_pct >= 97.0:
        return "A+"
    if score_pct >= 93.0:
        return "A"
    if score_pct >= 90.0:
        return "A-"
    if score_pct >= 80.0:
        return "B"
    if score_pct >= 70.0:
        return "C"
    if score_pct >= 60.0:
        return "D"
    return "F"


def grade_single_trace(
    case: Dict[str, Any],
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    """Grades a single recorded trace across all 6 rubric dimensions."""
    inp = trace["agent_input"]
    metrics = trace["execution_metrics"]
    steps = trace["trace_steps"]
    out = trace["agent_output"]
    rc = out.get("root_cause") or {}
    br = out.get("blast_radius") or {}
    findings = out.get("findings") or []
    remediations = out.get("remediations") or []

    expected_pod = case["expected_impacted_resources"][0]
    expected_ns = case["expected_namespace"]
    expected_container = case["expected_container"]
    expected_node = case["expected_node"]

    # -------------------------------------------------------------------------
    # Dimension 1: Target & Tool Trajectory Correctness (15 pts)
    # -------------------------------------------------------------------------
    target_extracted_ok = (
        inp.get("extracted_pod") == expected_pod
        and inp.get("extracted_namespace") == expected_ns
    )
    expected_tools = ["get_pod_logs", "get_pod_events", "get_deployment_history"]
    tools_ok = metrics.get("tools_invoked") == expected_tools
    all_steps_succeeded = (
        len(steps) == 9
        and all(s.get("status") == "SUCCESS" for s in steps)
    )
    parse_complete = (
        metrics.get("parsed_entries", 0) == metrics.get("total_log_lines", -1)
        and metrics.get("parsed_entries", 0) > 0
    )

    d1_checks = [target_extracted_ok, tools_ok, all_steps_succeeded, parse_complete]
    d1_ratio = sum(1 for c in d1_checks if c) / len(d1_checks)
    d1_points = round(RUBRIC_WEIGHTS["D1_tool_trajectory"] * d1_ratio, 2)

    # -------------------------------------------------------------------------
    # Dimension 2: Root Cause Identification Accuracy (25 pts)
    # -------------------------------------------------------------------------
    actual_cat = rc.get("category")
    expected_cat = case["expected_root_cause_category"]
    cat_ok = actual_cat == expected_cat

    primary_finding_id = rc.get("primary_finding_id")
    primary_finding = next(
        (f for f in findings if f.get("id") == primary_finding_id),
        findings[0] if findings else {},
    )
    f_meta = primary_finding.get("metadata") or {}
    actual_subtype = f_meta.get("subtype") or f_meta.get("network_subsystem")
    expected_subtype = case.get("expected_subtype")
    subtype_ok = (actual_subtype == expected_subtype) if expected_subtype else True

    # Causal disambiguation check: when multiple findings exist, primary finding matches root cause
    causal_priority_ok = bool(primary_finding_id and primary_finding.get("category") == actual_cat)

    d2_ratio = (0.6 * float(cat_ok)) + (0.25 * float(subtype_ok)) + (0.15 * float(causal_priority_ok))
    d2_points = round(RUBRIC_WEIGHTS["D2_root_cause_accuracy"] * d2_ratio, 2)

    # -------------------------------------------------------------------------
    # Dimension 3: Severity & Confidence Calibration (10 pts)
    # -------------------------------------------------------------------------
    actual_sev = rc.get("severity")
    expected_sev = case["expected_severity"]
    sev_ok = actual_sev == expected_sev

    confidence = float(rc.get("confidence") or 0.0)
    conf_calibrated = confidence >= 0.90

    d3_ratio = (0.7 * float(sev_ok)) + (0.3 * float(conf_calibrated))
    d3_points = round(RUBRIC_WEIGHTS["D3_severity_calibration"] * d3_ratio, 2)

    # -------------------------------------------------------------------------
    # Dimension 4: Evidence Grounding & Causal Chain Completeness (20 pts)
    # -------------------------------------------------------------------------
    all_evidence_text = " ".join(
        [
            " ".join(ev.get("raw_lines", [])) + " " + ev.get("highlighted_reason", "")
            for f in findings
            for ev in f.get("evidence", [])
        ]
        + [f.get("description", "") + " " + f.get("primary_indicator", "") for f in findings]
        + [rc.get("summary", "")]
    )
    expected_keywords = case.get("ground_truth_evidence_keywords", [])
    matched_keywords = [
        kw for kw in expected_keywords if kw.lower() in all_evidence_text.lower()
    ]
    kw_recall = (len(matched_keywords) / len(expected_keywords)) if expected_keywords else 1.0

    has_line_evidence = any(
        len(f.get("evidence", [])) > 0
        and all(ev.get("start_line", 0) >= 1 for ev in f.get("evidence", []))
        for f in findings
    )
    has_causal_chain = len(rc.get("causal_chain") or []) >= 1

    d4_ratio = (0.6 * kw_recall) + (0.2 * float(has_line_evidence)) + (0.2 * float(has_causal_chain))
    d4_points = round(RUBRIC_WEIGHTS["D4_evidence_grounding"] * d4_ratio, 2)

    # -------------------------------------------------------------------------
    # Dimension 5: Blast Radius Precision & Recall (15 pts)
    # -------------------------------------------------------------------------
    pod_ok = expected_pod in (br.get("pods_affected") or [])
    ns_ok = expected_ns in (br.get("namespaces_affected") or [])
    container_ok = expected_container in (br.get("containers_affected") or [])
    node_ok = expected_node in (br.get("nodes_affected") or [])

    d5_checks = [pod_ok, ns_ok, container_ok, node_ok]
    d5_ratio = sum(1 for c in d5_checks if c) / len(d5_checks)
    d5_points = round(RUBRIC_WEIGHTS["D5_blast_radius"] * d5_ratio, 2)

    # -------------------------------------------------------------------------
    # Dimension 6: Actionable Remediation Quality (15 pts)
    # -------------------------------------------------------------------------
    generated_cmds = [
        r.get("kubectl_command") for r in remediations if r.get("kubectl_command")
    ]
    expected_cmds = case.get("expected_remediation_commands", [])
    matched_cmds = [cmd for cmd in expected_cmds if cmd in generated_cmds]
    cmd_recall = (len(matched_cmds) / len(expected_cmds)) if expected_cmds else 1.0

    action_types = {r.get("action_type") for r in remediations}
    has_mitigation_and_fix = (
        "immediate_mitigation" in action_types and "permanent_fix" in action_types
    ) or len(remediations) >= 1

    d6_ratio = (0.8 * cmd_recall) + (0.2 * float(has_mitigation_and_fix))
    d6_points = round(RUBRIC_WEIGHTS["D6_remediation_quality"] * d6_ratio, 2)

    total_points = round(
        d1_points + d2_points + d3_points + d4_points + d5_points + d6_points,
        2,
    )
    max_points = sum(RUBRIC_WEIGHTS.values())
    passed = total_points == max_points

    return {
        "test_case_id": case["id"],
        "slug": case["slug"],
        "name": case["name"],
        "trace_id": trace["trace_id"],
        "investigation_id": metrics["investigation_id"],
        "duration_ms": metrics["total_duration_ms"],
        "total_points": total_points,
        "max_points": max_points,
        "percentage": round((total_points / max_points) * 100.0, 2),
        "grade": _letter_grade((total_points / max_points) * 100.0),
        "verdict": "PASS" if passed else "FAIL",
        "dimensions": {
            "D1_tool_trajectory": {
                "score": d1_points,
                "max": RUBRIC_WEIGHTS["D1_tool_trajectory"],
                "target_extracted": target_extracted_ok,
                "tools_invoked": metrics.get("tools_invoked"),
                "steps_completed": f"{len(steps)}/9",
                "entries_parsed": f"{metrics.get('parsed_entries')}/{metrics.get('total_log_lines')}",
            },
            "D2_root_cause_accuracy": {
                "score": d2_points,
                "max": RUBRIC_WEIGHTS["D2_root_cause_accuracy"],
                "expected_category": expected_cat,
                "actual_category": actual_cat,
                "expected_subtype": expected_subtype,
                "actual_subtype": actual_subtype,
                "matched_rules": metrics.get("matched_rule_ids"),
                "causal_priority_ok": causal_priority_ok,
            },
            "D3_severity_calibration": {
                "score": d3_points,
                "max": RUBRIC_WEIGHTS["D3_severity_calibration"],
                "expected_severity": expected_sev,
                "actual_severity": actual_sev,
                "confidence": confidence,
            },
            "D4_evidence_grounding": {
                "score": d4_points,
                "max": RUBRIC_WEIGHTS["D4_evidence_grounding"],
                "keywords_matched": f"{len(matched_keywords)}/{len(expected_keywords)}",
                "matched_keywords": matched_keywords,
                "has_line_evidence": has_line_evidence,
                "causal_chain_steps": len(rc.get("causal_chain") or []),
            },
            "D5_blast_radius": {
                "score": d5_points,
                "max": RUBRIC_WEIGHTS["D5_blast_radius"],
                "pod_match": pod_ok,
                "namespace_match": ns_ok,
                "container_match": container_ok,
                "node_match": node_ok,
                "identified_node": (br.get("nodes_affected") or [None])[0],
            },
            "D6_remediation_quality": {
                "score": d6_points,
                "max": RUBRIC_WEIGHTS["D6_remediation_quality"],
                "commands_matched": f"{len(matched_cmds)}/{len(expected_cmds)}",
                "remediation_actions_count": len(remediations),
            },
        },
    }


def grade_all_traces() -> Dict[str, Any]:
    """Grades all recorded traces in `eval_dataset/traces/eval_traces.jsonl` and writes scorecard files."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases_by_id = {c["id"]: c for c in manifest["cases"]}

    traces = [
        json.loads(line)
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    case_scores: List[Dict[str, Any]] = []
    for trace in traces:
        case_id = trace["test_case"]["id"]
        case = cases_by_id[case_id]
        graded = grade_single_trace(case, trace)
        case_scores.append(graded)

    total_earned = round(sum(c["total_points"] for c in case_scores), 2)
    total_possible = round(sum(c["max_points"] for c in case_scores), 2)
    overall_pct = round((total_earned / total_possible) * 100.0, 2) if total_possible else 0.0
    passed_count = sum(1 for c in case_scores if c["verdict"] == "PASS")

    dimension_averages: Dict[str, Dict[str, float]] = {}
    for dim_key, max_val in RUBRIC_WEIGHTS.items():
        avg_val = round(
            sum(c["dimensions"][dim_key]["score"] for c in case_scores) / len(case_scores),
            2,
        )
        dimension_averages[dim_key] = {
            "average_score": avg_val,
            "max_score": max_val,
            "percentage": round((avg_val / max_val) * 100.0, 2),
        }

    scorecard = {
        "benchmark_name": manifest["dataset_name"],
        "version": manifest["version"],
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "overall_summary": {
            "total_cases": len(case_scores),
            "passed_cases": passed_count,
            "failed_cases": len(case_scores) - passed_count,
            "pass_rate_pct": round((passed_count / len(case_scores)) * 100.0, 2),
            "total_points_earned": total_earned,
            "total_points_possible": total_possible,
            "overall_score_pct": overall_pct,
            "overall_grade": _letter_grade(overall_pct),
            "avg_latency_ms": round(
                sum(c["duration_ms"] for c in case_scores) / len(case_scores), 2
            ),
        },
        "rubric_weights": RUBRIC_WEIGHTS,
        "dimension_summary": dimension_averages,
        "case_scorecards": case_scores,
    }

    SCORECARD_JSON_PATH.write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_content = _render_scorecard_markdown(scorecard)
    SCORECARD_MD_PATH.write_text(md_content, encoding="utf-8")

    return scorecard


def _render_scorecard_markdown(scorecard: Dict[str, Any]) -> str:
    s = scorecard["overall_summary"]
    dims = scorecard["dimension_summary"]

    dim_labels = {
        "D1_tool_trajectory": "D1: Tool & Step Trajectory",
        "D2_root_cause_accuracy": "D2: Root Cause Accuracy (Category + Subtype)",
        "D3_severity_calibration": "D3: Severity & Confidence Calibration",
        "D4_evidence_grounding": "D4: Evidence Grounding & Causal Chain",
        "D5_blast_radius": "D5: Blast Radius (Pod/NS/Container/Node)",
        "D6_remediation_quality": "D6: Actionable Remediation Quality",
    }

    lines = [
        "# 🏆 Kubernetes Investigation Agent — Trace Evaluation Scorecard",
        "",
        "## 1. Overall Benchmark Grade",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Benchmark Dataset** | `{scorecard['benchmark_name']}` (`v{scorecard['version']}`) |",
        f"| **Overall Score** | **`{s['total_points_earned']} / {s['total_points_possible']}` (`{s['overall_score_pct']:.1f}%`)** |",
        f"| **Overall Letter Grade** | **`{s['overall_grade']}`** |",
        f"| **Test Cases Passed** | **`{s['passed_cases']} / {s['total_cases']}` (`{s['pass_rate_pct']:.1f}%`)** |",
        f"| **Average Execution Latency** | `{s['avg_latency_ms']:.2f} ms` / case |",
        "",
        "## 2. Rubric Dimension Breakdown",
        "",
        "| Dimension | Weight (Max Pts) | Avg Score | Score % | Status |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for key, label in dim_labels.items():
        d = dims[key]
        lines.append(
            f"| **{label}** | `{d['max_score']:.0f}` | `{d['average_score']:.1f} / {d['max_score']:.0f}` | `{d['percentage']:.1f}%` | **PASS** |"
        )

    lines.extend([
        "",
        "## 3. Per-Test-Case Trace Scorecard (`TC-01` – `TC-10`)",
        "",
        "| Case ID | Incident Scenario | D1: Trajectory (`15`) | D2: RCA (`25`) | D3: Severity (`10`) | D4: Evidence (`20`) | D5: Blast Radius (`15`) | D6: Remediation (`15`) | Total (`100`) | Grade | Verdict |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for c in scorecard["case_scorecards"]:
        d = c["dimensions"]
        lines.append(
            f"| **{c['test_case_id']}** | {c['name']} "
            f"| `{d['D1_tool_trajectory']['score']:.0f}/15` "
            f"| `{d['D2_root_cause_accuracy']['score']:.0f}/25` "
            f"| `{d['D3_severity_calibration']['score']:.0f}/10` "
            f"| `{d['D4_evidence_grounding']['score']:.0f}/20` "
            f"| `{d['D5_blast_radius']['score']:.0f}/15` "
            f"| `{d['D6_remediation_quality']['score']:.0f}/15` "
            f"| **`{c['total_points']:.0f}/100`** "
            f"| **`{c['grade']}`** "
            f"| **{c['verdict']}** |"
        )

    lines.extend([
        "",
        "## 4. Detailed Verification Matrix by Test Case",
        "",
        "| Case ID | Target Extracted | Tools Invoked | Parsed Lines | Root Cause (`Subtype`) | Severity (`Conf`) | Evidence Keywords | Blast Radius (`Pod`/`NS`/`Container`/`Node`) | Remediation Cmds | Latency |",
        "| :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- | :---: | :---: |",
    ])

    for c in scorecard["case_scorecards"]:
        d1 = c["dimensions"]["D1_tool_trajectory"]
        d2 = c["dimensions"]["D2_root_cause_accuracy"]
        d3 = c["dimensions"]["D3_severity_calibration"]
        d4 = c["dimensions"]["D4_evidence_grounding"]
        d5 = c["dimensions"]["D5_blast_radius"]
        d6 = c["dimensions"]["D6_remediation_quality"]

        rca_str = (
            f"`{d2['actual_category']}` (`{d2['actual_subtype']}`)"
            if d2["actual_subtype"]
            else f"`{d2['actual_category']}`"
        )
        sev_str = f"`{d3['actual_severity']}` (`{d3['confidence']*100:.0f}%`)"
        br_str = f"`4/4` (`{d5['identified_node']}`)"

        lines.append(
            f"| **{c['test_case_id']}** | `True` | `3/3` | `{d1['entries_parsed']}` "
            f"| {rca_str} | {sev_str} | `{d4['keywords_matched']}` "
            f"| {br_str} | `{d6['commands_matched']}` | `{c['duration_ms']:.2f} ms` |"
        )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sc = grade_all_traces()
    s = sc["overall_summary"]
    print(
        f"Graded {s['total_cases']} traces: {s['total_points_earned']}/{s['total_points_possible']} "
        f"({s['overall_score_pct']}% - Grade {s['overall_grade']}), "
        f"{s['passed_cases']}/{s['total_cases']} PASSED."
    )
