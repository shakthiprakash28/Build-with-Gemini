"""
Executes the KubernetesInvestigationAgent across all 10 synthesized Kubernetes incident
test cases in `eval_dataset/eval_cases.json` and generates structured execution traces.

Generated artifacts in `eval_dataset/traces/`:
  - `tc01_oom_kill_trace.json` ... `tc10_service_routes_unhealthy_pods_trace.json` (per-case full traces)
  - `eval_traces.jsonl` (JSON Lines stream of all 10 execution traces)
  - `trace_summary.json` (aggregated benchmark & trace metrics)
  - `TRACE_REPORT.md` (human-readable Markdown trace & evaluation report)
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from k8s_investigate.agent import KubernetesInvestigationAgent


EVAL_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = EVAL_DIR / "eval_cases.json"
TRACES_DIR = EVAL_DIR / "traces"


def _extract_event_lines(raw_log_text: str) -> str:
    """Extracts Kubernetes event and control-plane diagnostic lines from the incident log."""
    event_keywords = (
        "Warning ",
        "Normal ",
        "FailedScheduling",
        "BackOff",
        "OOMKilled",
        "Evicted",
        "NodeNotReady",
        "MemoryPressure",
        "Readiness probe failed",
        "no endpoints available",
        "publishNotReadyAddresses",
        "Endpoints:",
        "EndpointSlice",
        "Last State:",
        "terminated with exit code",
        "CFS quota exceeded",
    )
    lines = [
        line
        for line in raw_log_text.splitlines()
        if any(kw.lower() in line.lower() for kw in event_keywords)
    ]
    return "\n".join(lines) if lines else raw_log_text


def _build_deployment_history(case: Dict[str, Any], raw_log_text: str) -> str:
    """Synthesizes deployment rollout history output matching the workload in the test case."""
    pod_name = case["expected_impacted_resources"][0]
    container_name = case["expected_container"]
    hash_match = re.match(
        r"^([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)-[a-z0-9]{5,10}-[a-z0-9]{4,6}$",
        pod_name,
        re.IGNORECASE,
    )
    deploy_name = hash_match.group(1) if hash_match else pod_name

    # Extract version or image if mentioned in log
    img_match = re.search(r'image\s+"([^"]+)"', raw_log_text, re.IGNORECASE)
    ver_match = re.search(r"\b(v\d+\.\d+\.\d+)\b", raw_log_text)
    if img_match:
        image_str = img_match.group(1)
    elif ver_match:
        image_str = f"registry.internal/{case['expected_namespace']}/{container_name}:{ver_match.group(1)}"
    else:
        image_str = f"registry.internal/{case['expected_namespace']}/{container_name}:v1.0.0"

    return (
        f"deployment.apps/{deploy_name}\n"
        f"REVISION  CHANGE-CAUSE\n"
        f"1         kubectl apply --filename={deploy_name}-deployment.yaml\n"
        f"deployment.apps/{deploy_name} with revision #1\n"
        f"Pod Template:\n"
        f"  Containers:\n"
        f"   {container_name}:\n"
        f"    Image:      {image_str}\n"
    )


def evaluate_against_ground_truth(
    case: Dict[str, Any],
    report_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Compares the agent's InvestigationReport against the test case ground truth."""
    root_cause = report_dict.get("root_cause") or {}
    findings = report_dict.get("findings") or []
    blast_radius = report_dict.get("blast_radius") or {}
    remediations = report_dict.get("remediations") or []

    actual_category = root_cause.get("category")
    expected_category = case["expected_root_cause_category"]
    category_match = actual_category == expected_category

    actual_severity = root_cause.get("severity")
    expected_severity = case["expected_severity"]
    severity_match = actual_severity == expected_severity

    # Subtype check
    primary_finding_id = root_cause.get("primary_finding_id")
    primary_finding = next(
        (f for f in findings if f.get("id") == primary_finding_id),
        findings[0] if findings else {},
    )
    metadata = primary_finding.get("metadata") or {}
    actual_subtype = metadata.get("subtype") or metadata.get("network_subsystem")
    expected_subtype = case.get("expected_subtype")
    subtype_match = (actual_subtype == expected_subtype) if expected_subtype else True

    # Blast radius check
    pods_affected = blast_radius.get("pods_affected") or []
    namespaces_affected = blast_radius.get("namespaces_affected") or []
    containers_affected = blast_radius.get("containers_affected") or []

    pod_match = all(p in pods_affected for p in case["expected_impacted_resources"])
    ns_match = case["expected_namespace"] in namespaces_affected
    container_match = case["expected_container"] in containers_affected
    blast_radius_match = pod_match and ns_match and container_match

    # Evidence keywords check
    all_evidence_text = " ".join(
        [
            " ".join(ev.get("raw_lines", [])) + " " + ev.get("highlighted_reason", "")
            for f in findings
            for ev in f.get("evidence", [])
        ]
        + [f.get("description", "") + " " + f.get("primary_indicator", "") for f in findings]
        + [root_cause.get("summary", "")]
    )
    matched_keywords = [
        kw for kw in case.get("ground_truth_evidence_keywords", [])
        if kw.lower() in all_evidence_text.lower()
    ]
    evidence_match = len(matched_keywords) == len(case.get("ground_truth_evidence_keywords", []))

    # Remediation commands check
    generated_commands = [
        r.get("kubectl_command") for r in remediations if r.get("kubectl_command")
    ]
    matched_remediations = [
        cmd for cmd in case.get("expected_remediation_commands", [])
        if cmd in generated_commands
    ]
    remediation_match = len(matched_remediations) == len(case.get("expected_remediation_commands", []))

    checks = [
        category_match,
        subtype_match,
        severity_match,
        blast_radius_match,
        evidence_match,
        remediation_match,
    ]
    score = round(sum(1 for c in checks if c) / len(checks), 4)
    passed = all(checks)

    return {
        "passed": passed,
        "score": score,
        "checks": {
            "root_cause_category": {
                "expected": expected_category,
                "actual": actual_category,
                "matched": category_match,
            },
            "subtype": {
                "expected": expected_subtype,
                "actual": actual_subtype,
                "matched": subtype_match,
            },
            "severity": {
                "expected": expected_severity,
                "actual": actual_severity,
                "matched": severity_match,
            },
            "blast_radius": {
                "expected_pods": case["expected_impacted_resources"],
                "actual_pods": pods_affected,
                "expected_namespace": case["expected_namespace"],
                "actual_namespaces": namespaces_affected,
                "expected_container": case["expected_container"],
                "actual_containers": containers_affected,
                "matched": blast_radius_match,
            },
            "evidence_keywords": {
                "expected": case.get("ground_truth_evidence_keywords", []),
                "matched_keywords": matched_keywords,
                "matched": evidence_match,
            },
            "remediation_commands": {
                "expected": case.get("expected_remediation_commands", []),
                "matched_commands": matched_remediations,
                "all_generated_commands": generated_commands,
                "matched": remediation_match,
            },
        },
    }


def run_all_eval_traces() -> Dict[str, Any]:
    """Executes the agent across all 10 dataset test cases and writes trace files."""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = manifest["cases"]

    suite_started_at = datetime.now(timezone.utc).isoformat()
    t_suite_0 = time.perf_counter()

    all_traces: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases, start=1):
        case_id = case["id"]
        slug = case["slug"]
        log_path = EVAL_DIR / case["log_file"]
        raw_log_text = log_path.read_text(encoding="utf-8")

        target_pod = case["expected_impacted_resources"][0]
        target_ns = case["expected_namespace"]
        target_container = case["expected_container"]

        event_lines_text = _extract_event_lines(raw_log_text)
        history_text = _build_deployment_history(case, raw_log_text)

        agent = KubernetesInvestigationAgent(
            pod_log_tool=lambda pod_name, namespace="default", **kwargs: raw_log_text,
            pod_event_tool=lambda pod_name, namespace="default", **kwargs: event_lines_text,
            deployment_history_tool=lambda deployment_name="", namespace="default", **kwargs: history_text,
        )

        prompt = f"Investigate the Kubernetes incident for pod {target_pod} in namespace {target_ns}"
        report, agent_trace = agent.investigate_with_trace(
            source=prompt,
            container=target_container,
        )

        report_dict = report.to_dict()
        eval_verdict = evaluate_against_ground_truth(case, report_dict)

        trace_filename = f"{case_id.lower().replace('-', '')}_{slug}_trace.json"
        trace_file_path = TRACES_DIR / trace_filename

        full_trace_record = {
            "trace_id": f"trace-{case_id.lower()}-{slug}",
            "sequence_number": idx,
            "test_case": {
                "id": case_id,
                "slug": slug,
                "name": case["name"],
                "log_file": case["log_file"],
                "scenario_description": case["scenario_description"],
                "injected_fault": case["injected_fault"],
                "ground_truth_rca": case["ground_truth_rca"],
            },
            "agent_input": {
                "prompt": prompt,
                "extracted_pod": agent_trace["target"]["pod_name"],
                "extracted_namespace": agent_trace["target"]["namespace"],
                "container": target_container,
            },
            "execution_metrics": {
                "investigation_id": report.investigation_id,
                "started_at": agent_trace["started_at"],
                "completed_at": agent_trace["completed_at"],
                "total_duration_ms": agent_trace["total_duration_ms"],
                "engine_duration_ms": agent_trace["engine_trace"]["phase_timings_ms"]["total_engine_ms"],
                "phase_timings_ms": agent_trace["engine_trace"]["phase_timings_ms"],
                "total_steps": len(agent_trace["steps"]),
                "tools_invoked_count": len(agent_trace["tools_invoked"]),
                "tools_invoked": agent_trace["tools_invoked"],
                "total_log_lines": report.total_log_lines,
                "parsed_entries": report.parsed_entries,
                "rules_evaluated": agent_trace["engine_trace"]["rules_evaluated_count"],
                "rules_matched": agent_trace["engine_trace"]["rules_matched_count"],
                "matched_rule_ids": agent_trace["engine_trace"]["matched_rule_ids"],
            },
            "trace_steps": agent_trace["steps"],
            "agent_output": {
                "overall_status": report.overall_status,
                "root_cause": report_dict["root_cause"],
                "blast_radius": report_dict["blast_radius"],
                "findings": report_dict["findings"],
                "timeline": report_dict["timeline"],
                "remediations": report_dict["remediations"],
            },
            "evaluation": eval_verdict,
        }

        trace_file_path.write_text(
            json.dumps(full_trace_record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        all_traces.append(full_trace_record)

        summary_rows.append({
            "test_case_id": case_id,
            "slug": slug,
            "name": case["name"],
            "trace_file": f"traces/{trace_filename}",
            "prompt": prompt,
            "tools_invoked": agent_trace["tools_invoked"],
            "total_steps": len(agent_trace["steps"]),
            "parsed_entries": report.parsed_entries,
            "matched_rules": agent_trace["engine_trace"]["matched_rule_ids"],
            "predicted_category": eval_verdict["checks"]["root_cause_category"]["actual"],
            "expected_category": eval_verdict["checks"]["root_cause_category"]["expected"],
            "predicted_subtype": eval_verdict["checks"]["subtype"]["actual"],
            "expected_subtype": eval_verdict["checks"]["subtype"]["expected"],
            "predicted_severity": eval_verdict["checks"]["severity"]["actual"],
            "confidence": report.root_cause.confidence if report.root_cause else 0.0,
            "remediations_count": len(report.remediations),
            "duration_ms": agent_trace["total_duration_ms"],
            "passed": eval_verdict["passed"],
            "score": eval_verdict["score"],
        })

    suite_duration_ms = round((time.perf_counter() - t_suite_0) * 1000.0, 4)
    suite_completed_at = datetime.now(timezone.utc).isoformat()

    # Write combined JSONL trace file
    jsonl_path = TRACES_DIR / "eval_traces.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for tr in all_traces:
            f.write(json.dumps(tr, ensure_ascii=False) + "\n")

    passed_count = sum(1 for r in summary_rows if r["passed"])
    avg_duration_ms = round(
        sum(r["duration_ms"] for r in summary_rows) / len(summary_rows), 4
    )

    summary_payload = {
        "dataset_name": manifest["dataset_name"],
        "version": manifest["version"],
        "suite_started_at": suite_started_at,
        "suite_completed_at": suite_completed_at,
        "suite_total_duration_ms": suite_duration_ms,
        "average_case_duration_ms": avg_duration_ms,
        "total_cases": len(summary_rows),
        "passed_cases": passed_count,
        "failed_cases": len(summary_rows) - passed_count,
        "accuracy_rate": round(passed_count / len(summary_rows), 4),
        "total_tool_calls": sum(len(r["tools_invoked"]) for r in summary_rows),
        "total_trace_steps": sum(r["total_steps"] for r in summary_rows),
        "total_rules_evaluated": sum(
            tr["execution_metrics"]["rules_evaluated"] for tr in all_traces
        ),
        "cases": summary_rows,
    }

    summary_path = TRACES_DIR / "trace_summary.json"
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Write Markdown Trace & Evaluation Report
    md_report = _render_markdown_trace_report(summary_payload, all_traces)
    md_path = TRACES_DIR / "TRACE_REPORT.md"
    md_path.write_text(md_report, encoding="utf-8")

    return summary_payload


def _render_markdown_trace_report(
    summary: Dict[str, Any],
    traces: List[Dict[str, Any]],
) -> str:
    """Renders a comprehensive Markdown report of all 10 agent execution traces."""
    lines: List[str] = [
        "# 🔍 Kubernetes Investigation Agent — Evaluation Dataset Execution Traces",
        "",
        "## 1. Executive Benchmark Summary",
        "",
        f"- **Dataset**: `{summary['dataset_name']}` (`v{summary['version']}`)",
        f"- **Total Test Cases Executed**: `{summary['total_cases']}`",
        f"- **Passed Cases**: `{summary['passed_cases']} / {summary['total_cases']}` (**{summary['accuracy_rate'] * 100:.1f}%** accuracy)",
        f"- **Total Agent Trace Steps Recorded**: `{summary['total_trace_steps']}` (`9` steps per case)",
        f"- **Total Cluster Tool Invocations**: `{summary['total_tool_calls']}` (`get_pod_logs`, `get_pod_events`, `get_deployment_history` per case)",
        f"- **Total Diagnostic Rule Evaluations**: `{summary['total_rules_evaluated']}` (`9` rules × `10` cases)",
        f"- **Total Suite Execution Time**: `{summary['suite_total_duration_ms']:.2f} ms` (avg `{summary['average_case_duration_ms']:.2f} ms` / case)",
        "",
        "## 2. Summary of Executed Test Cases & Traces",
        "",
        "| ID | Incident Scenario | Target Pod (`Namespace`) | Tools Invoked | Matched Rules | Root Cause (`Subtype`) | Severity | Confidence | Latency | Verdict | Trace File |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for tr in traces:
        tc = tr["test_case"]
        metrics = tr["execution_metrics"]
        ev = tr["evaluation"]
        rc = tr["agent_output"]["root_cause"]
        cat_str = ev["checks"]["root_cause_category"]["actual"]
        sub_str = ev["checks"]["subtype"]["actual"]
        cat_display = f"`{cat_str}` (`{sub_str}`)" if sub_str else f"`{cat_str}`"
        verdict_str = "PASS (100%)" if ev["passed"] else f"FAIL ({ev['score']*100:.0f}%)"
        trace_fname = f"{tc['id'].lower().replace('-', '')}_{tc['slug']}_trace.json"
        lines.append(
            f"| **{tc['id']}** | {tc['name']} | `{tr['agent_input']['extracted_pod']}` (`{tr['agent_input']['extracted_namespace']}`) "
            f"| `{', '.join(metrics['tools_invoked'])}` | `{', '.join(metrics['matched_rule_ids'])}` "
            f"| {cat_display} | `{rc['severity']}` | `{rc['confidence']*100:.0f}%` "
            f"| `{metrics['total_duration_ms']:.2f} ms` | **{verdict_str}** | `{trace_fname}` |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Detailed Step-by-Step Execution Traces",
        "",
    ])

    for tr in traces:
        tc = tr["test_case"]
        inp = tr["agent_input"]
        metrics = tr["execution_metrics"]
        out = tr["agent_output"]
        rc = out["root_cause"]
        br = out["blast_radius"]
        ev = tr["evaluation"]

        lines.extend([
            f"### {tc['id']}: {tc['name']} (`{tr['trace_id']}`)",
            "",
            f"- **Input Prompt**: `\"{inp['prompt']}\"`",
            f"- **Source Log File**: `{tc['log_file']}` (`{metrics['total_log_lines']}` lines -> `{metrics['parsed_entries']}` parsed entries)",
            f"- **Investigation ID**: `{metrics['investigation_id']}`",
            f"- **Execution Latency**: `{metrics['total_duration_ms']:.2f} ms`",
            "",
            "#### Agent Execution Step Trace",
            "",
            "| Step | Step Type | Component / Tool | Status | Duration (ms) | Key Output / Observation |",
            "| :---: | :--- | :--- | :---: | :---: | :--- |",
        ])

        for step in tr["trace_steps"]:
            s_idx = step["step_index"]
            s_type = step["step_type"]
            comp = step.get("tool_name") or step.get("component", "")
            status = step["status"]
            dur = step["duration_ms"]

            if s_type == "target_extraction":
                obs = f"Extracted pod=`{step['output']['pod_name']}`, namespace=`{step['output']['namespace']}`"
            elif s_type == "tool_call":
                summary_info = step.get("output_summary", {})
                obs = f"Fetched `{summary_info.get('line_count', 0)}` lines (`{summary_info.get('char_count', 0)}` chars)"
            elif s_type == "log_parsing":
                summary_info = step.get("output_summary", {})
                obs = (
                    f"Parsed `{summary_info.get('parsed_entries_count', 0)}` entries; "
                    f"levels=`{summary_info.get('level_distribution')}`; "
                    f"components=`{summary_info.get('detected_components')}`"
                )
            elif s_type == "diagnostic_rule_evaluation":
                obs = (
                    f"Evaluated `{step['rules_evaluated_count']}` rules -> "
                    f"matched `{step['rules_matched_count']}`: `{step['matched_rule_ids']}`"
                )
            elif s_type == "causal_root_cause_resolution":
                s_out = step["output_summary"]
                sub_note = f" / `{s_out['subtype']}`" if s_out.get("subtype") else ""
                obs = f"Primary RCA: `{s_out['category']}`{sub_note} (`{s_out['severity']}`, conf=`{s_out['confidence']}`)"
            elif s_type == "blast_radius_computation":
                s_out = step["output_summary"]
                obs = (
                    f"Pods=`{s_out['pods_affected']}`, NS=`{s_out['namespaces_affected']}`, "
                    f"Containers=`{s_out['containers_affected']}`, Nodes=`{s_out['nodes_affected']}`"
                )
            elif s_type == "remediation_generation":
                s_out = step["output_summary"]
                obs = f"Generated `{s_out['remediation_count']}` remediation actions"
            else:
                obs = ""

            lines.append(f"| {s_idx} | `{s_type}` | `{comp}` | `{status}` | `{dur:.3f}` | {obs} |")

        lines.extend([
            "",
            "#### Root Cause & Causal Chain",
            f"- **Root Cause Summary**: {rc['summary']}",
            "- **Causal Chain**:",
        ])
        for c_step in rc.get("causal_chain", []):
            lines.append(f"  1. {c_step}")

        lines.extend([
            "",
            "#### Generated Remediation Commands",
        ])
        for rem in out.get("remediations", []):
            if rem.get("kubectl_command"):
                lines.append(f"- **[{rem['action_type'].upper()}]** {rem['description']}: `{rem['kubectl_command']}`")

        lines.extend([
            "",
            "#### Ground-Truth Evaluation Checks",
            f"- **Category Match**: `{ev['checks']['root_cause_category']['actual']}` == `{ev['checks']['root_cause_category']['expected']}` (`{ev['checks']['root_cause_category']['matched']}`)",
            f"- **Subtype Match**: `{ev['checks']['subtype']['actual']}` == `{ev['checks']['subtype']['expected']}` (`{ev['checks']['subtype']['matched']}`)",
            f"- **Severity Match**: `{ev['checks']['severity']['actual']}` == `{ev['checks']['severity']['expected']}` (`{ev['checks']['severity']['matched']}`)",
            f"- **Blast Radius Match**: `{ev['checks']['blast_radius']['matched']}`",
            f"- **Evidence Keywords Matched**: `{len(ev['checks']['evidence_keywords']['matched_keywords'])}/{len(ev['checks']['evidence_keywords']['expected'])}` (`{ev['checks']['evidence_keywords']['matched_keywords']}`)",
            f"- **Remediation Commands Matched**: `{len(ev['checks']['remediation_commands']['matched_commands'])}/{len(ev['checks']['remediation_commands']['expected'])}`",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    summary = run_all_eval_traces()
    print(
        f"Generated {summary['total_cases']} execution traces in {TRACES_DIR} "
        f"({summary['passed_cases']}/{summary['total_cases']} passed, "
        f"suite time: {summary['suite_total_duration_ms']:.2f} ms)."
    )
