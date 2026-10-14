"""
Main Kubernetes Investigation Agent.
Uses `get_pod_logs`, `get_pod_events`, and `get_deployment_history` tools to fetch logs,
events, and deployment version history of a specific Kubernetes Pod directly from the cluster,
identifies failure anomalies, computes causal root causes, extracts supporting evidence,
and provides actionable remediation guidance.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple, Union

from k8s_investigate.engine import InvestigationEngine
from k8s_investigate.llm import LLMAdvisor
from k8s_investigate.models import InvestigationReport, LogEntry
from k8s_investigate.parser import LogParser
from k8s_investigate.reporter import ReportRenderer
from k8s_investigate.tools import get_deployment_history, get_pod_events, get_pod_logs


PROMPT_STOP_WORDS = {
    "a", "an", "and", "analyze", "any", "application", "are", "as", "at", "attached",
    "back", "backoff", "be", "been", "broken", "by", "can", "cause", "change", "changes",
    "check", "cluster", "container", "containers", "crashed", "crashing", "crashloop",
    "crashloopbackoff", "current", "debug", "default", "deployment", "deployments",
    "describe", "diagnose", "do", "does", "down", "error", "errors", "event", "events",
    "explain", "fail", "failed", "failing", "failure", "failures", "fetch", "file", "find",
    "fix", "for", "from", "get", "get_deployment_history", "get_pod_events", "get_pod_logs",
    "give", "going", "happened", "happening", "has", "have", "health", "help", "history",
    "how", "i", "identify", "in", "incident", "info", "information", "input", "inspect",
    "into", "investigate", "investigation", "is", "issue", "issues", "it", "its", "k8s",
    "kubectl", "kubernetes", "log", "logs", "look", "me", "my", "name", "named",
    "namespace", "namespaces", "node", "not", "of", "on", "oom", "oomkilled",
    "or", "our", "out", "output", "please", "pod", "pods", "previous",
    "problem", "problems", "pull", "reason", "recent", "report", "resource", "resources",
    "restart", "restarting", "revision", "revisions", "rollout", "root", "run", "running",
    "see", "show", "specific", "start", "starting", "state", "status", "stuck", "tell",
    "that", "the", "their", "them", "there", "these", "this", "those", "to",
    "tool", "tools", "troubleshoot", "unable", "up", "use", "using", "version", "versions",
    "view", "waiting", "was", "what", "when", "where", "which", "why", "with", "within",
    "working", "wrong", "you", "your",
}

NAMESPACE_STOP_WORDS = {
    "a", "an", "current", "k8s", "kubernetes", "my", "our", "specific", "that",
    "the", "this", "target",
}


class KubernetesInvestigationAgent:
    """
    Autonomous Kubernetes Investigation Agent.
    Uses `get_pod_logs`, `get_pod_events`, and `get_deployment_history` tools to fetch logs,
    events, and deployment revision history from a Kubernetes Pod, identifies failure anomalies,
    computes causal root causes, extracts supporting evidence, and provides actionable remediation guidance.
    """

    def __init__(
        self,
        engine: Optional[InvestigationEngine] = None,
        parser: Optional[LogParser] = None,
        llm_advisor: Optional[LLMAdvisor] = None,
        renderer: Optional[ReportRenderer] = None,
        pod_log_tool: Optional[Callable[..., str]] = None,
        pod_event_tool: Optional[Callable[..., str]] = None,
        deployment_history_tool: Optional[Callable[..., str]] = None,
    ):
        self.parser = parser or LogParser()
        self.engine = engine or InvestigationEngine()
        self.llm_advisor = llm_advisor or LLMAdvisor()
        self.renderer = renderer or ReportRenderer()
        self.pod_log_tool = pod_log_tool
        self.pod_event_tool = pod_event_tool
        self.deployment_history_tool = deployment_history_tool
        self.tools = [get_pod_logs, get_pod_events, get_deployment_history]
        self.last_trace: Optional[Dict[str, Any]] = None

    def get_pod_logs(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        previous: bool = False,
        tail_lines: Optional[int] = None,
    ) -> str:
        """Invokes the `get_pod_logs` tool to fetch logs of a specific Kubernetes Pod."""
        target_ns = namespace or self.parser.default_namespace or "default"
        tool_fn = self.pod_log_tool or get_pod_logs
        return tool_fn(
            pod_name=pod_name,
            namespace=target_ns,
            container=container,
            previous=previous,
            tail_lines=tail_lines,
        )

    def get_pod_events(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> str:
        """Invokes the `get_pod_events` tool to fetch events of a specific Kubernetes Pod."""
        target_ns = namespace or self.parser.default_namespace or "default"
        tool_fn = self.pod_event_tool or get_pod_events
        return tool_fn(
            pod_name=pod_name,
            namespace=target_ns,
        )

    def get_deployment_history(
        self,
        deployment_name: str = "",
        namespace: Optional[str] = None,
        revision: Optional[int] = None,
        pod_name: Optional[str] = None,
    ) -> str:
        """Invokes the `get_deployment_history` tool to analyze recent changes in pod version or deployment revisions."""
        target_ns = namespace or self.parser.default_namespace or "default"
        tool_fn = self.deployment_history_tool or get_deployment_history
        target = deployment_name or pod_name or ""
        return tool_fn(
            deployment_name=target,
            namespace=target_ns,
            revision=revision,
            pod_name=pod_name or target,
        )

    def investigate_pod(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        previous: bool = False,
        tail_lines: Optional[int] = None,
        enable_llm: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> InvestigationReport:
        """
        Fetches logs, events, and deployment revision history for the specified Kubernetes Pod
        using `get_pod_logs`, `get_pod_events`, and `get_deployment_history` and runs the investigation.
        """
        import time
        from datetime import datetime, timezone

        t_start = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        target_ns = namespace or self.parser.default_namespace or "default"
        self.parser.default_namespace = target_ns

        collected_inputs: List[str] = []
        tool_errors: List[str] = []
        tools_used: List[str] = []
        history_text: str = ""
        trace_steps: List[Dict[str, Any]] = []
        tool_calls_trace: List[Dict[str, Any]] = []

        if context and context.get("_target_extraction_step"):
            trace_steps.append(context["_target_extraction_step"])

        all_default = (
            self.pod_log_tool is None
            and self.pod_event_tool is None
            and self.deployment_history_tool is None
        )

        if all_default or self.pod_log_tool is not None:
            t0 = time.perf_counter()
            tool_args = {
                "pod_name": pod_name,
                "namespace": target_ns,
                "container": container,
                "previous": previous,
                "tail_lines": tail_lines,
            }
            try:
                log_text = self.get_pod_logs(
                    pod_name=pod_name,
                    namespace=target_ns,
                    container=container,
                    previous=previous,
                    tail_lines=tail_lines,
                )
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                if log_text and log_text.strip():
                    stripped_logs = log_text.strip()
                    collected_inputs.append(stripped_logs)
                    tools_used.append("get_pod_logs")
                    lines_list = stripped_logs.splitlines()
                    step_info = {
                        "step_index": len(trace_steps) + 1,
                        "step_type": "tool_call",
                        "tool_name": "get_pod_logs",
                        "status": "SUCCESS",
                        "duration_ms": dur_ms,
                        "arguments": tool_args,
                        "output_summary": {
                            "line_count": len(lines_list),
                            "char_count": len(stripped_logs),
                            "preview_lines": lines_list[:5],
                        },
                    }
                    trace_steps.append(step_info)
                    tool_calls_trace.append(step_info)
            except Exception as exc:
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                tool_errors.append(str(exc))
                step_info = {
                    "step_index": len(trace_steps) + 1,
                    "step_type": "tool_call",
                    "tool_name": "get_pod_logs",
                    "status": "ERROR",
                    "duration_ms": dur_ms,
                    "arguments": tool_args,
                    "error": str(exc),
                }
                trace_steps.append(step_info)
                tool_calls_trace.append(step_info)

        if all_default or self.pod_event_tool is not None:
            t0 = time.perf_counter()
            tool_args = {"pod_name": pod_name, "namespace": target_ns}
            try:
                events_text = self.get_pod_events(
                    pod_name=pod_name,
                    namespace=target_ns,
                )
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                if events_text and events_text.strip():
                    stripped_events = events_text.strip()
                    ev_lines = stripped_events.splitlines()
                    existing_lines = {line for chunk in collected_inputs for line in chunk.splitlines()}
                    if stripped_events not in collected_inputs and not all(line in existing_lines for line in ev_lines):
                        collected_inputs.append(stripped_events)
                    tools_used.append("get_pod_events")
                    step_info = {
                        "step_index": len(trace_steps) + 1,
                        "step_type": "tool_call",
                        "tool_name": "get_pod_events",
                        "status": "SUCCESS",
                        "duration_ms": dur_ms,
                        "arguments": tool_args,
                        "output_summary": {
                            "line_count": len(ev_lines),
                            "char_count": len(stripped_events),
                            "preview_lines": ev_lines[:5],
                        },
                    }
                    trace_steps.append(step_info)
                    tool_calls_trace.append(step_info)
            except Exception as exc:
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                tool_errors.append(str(exc))
                step_info = {
                    "step_index": len(trace_steps) + 1,
                    "step_type": "tool_call",
                    "tool_name": "get_pod_events",
                    "status": "ERROR",
                    "duration_ms": dur_ms,
                    "arguments": tool_args,
                    "error": str(exc),
                }
                trace_steps.append(step_info)
                tool_calls_trace.append(step_info)

        if all_default or self.deployment_history_tool is not None:
            t0 = time.perf_counter()
            tool_args = {
                "deployment_name": pod_name,
                "namespace": target_ns,
                "pod_name": pod_name,
            }
            try:
                history_text = self.get_deployment_history(
                    deployment_name=pod_name,
                    namespace=target_ns,
                    pod_name=pod_name,
                )
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                if history_text and history_text.strip():
                    stripped_hist = history_text.strip()
                    tools_used.append("get_deployment_history")
                    if not collected_inputs:
                        collected_inputs.append(stripped_hist)
                    hist_lines = stripped_hist.splitlines()
                    step_info = {
                        "step_index": len(trace_steps) + 1,
                        "step_type": "tool_call",
                        "tool_name": "get_deployment_history",
                        "status": "SUCCESS",
                        "duration_ms": dur_ms,
                        "arguments": tool_args,
                        "output_summary": {
                            "line_count": len(hist_lines),
                            "char_count": len(stripped_hist),
                            "preview_lines": hist_lines[:5],
                        },
                    }
                    trace_steps.append(step_info)
                    tool_calls_trace.append(step_info)
            except Exception as exc:
                dur_ms = round((time.perf_counter() - t0) * 1000.0, 4)
                tool_errors.append(str(exc))
                step_info = {
                    "step_index": len(trace_steps) + 1,
                    "step_type": "tool_call",
                    "tool_name": "get_deployment_history",
                    "status": "ERROR",
                    "duration_ms": dur_ms,
                    "arguments": tool_args,
                    "error": str(exc),
                }
                trace_steps.append(step_info)
                tool_calls_trace.append(step_info)

        if not collected_inputs:
            err_msg = "; ".join(tool_errors) if tool_errors else f"No logs or events found for pod '{pod_name}'."
            raise RuntimeError(err_msg)

        t_parse_0 = time.perf_counter()
        combined_text = "\n".join(collected_inputs)
        entries = self.parser.parse_text(combined_text)

        # Ensure all parsed entries are associated with the target pod and namespace
        clean_pod = pod_name.split("/")[-1].strip()
        for entry in entries:
            if not entry.pod:
                entry.pod = clean_pod
            if not entry.namespace:
                entry.namespace = target_ns
            if container and not entry.container:
                entry.container = container
        t_parse_ms = round((time.perf_counter() - t_parse_0) * 1000.0, 4)

        level_counts: Dict[str, int] = {}
        components_seen: List[str] = []
        for entry in entries:
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
            if entry.component and entry.component not in components_seen:
                components_seen.append(entry.component)

        trace_steps.append({
            "step_index": len(trace_steps) + 1,
            "step_type": "log_parsing",
            "component": "LogParser.parse_text",
            "status": "SUCCESS",
            "duration_ms": t_parse_ms,
            "output_summary": {
                "total_raw_lines": entries[-1].line_number if entries else 0,
                "parsed_entries_count": len(entries),
                "level_distribution": level_counts,
                "detected_components": components_seen,
                "stack_trace_entries": sum(1 for e in entries if e.is_stack_trace),
            },
        })

        ctx = dict(context) if context else {}
        ctx["pod_name"] = clean_pod
        ctx["namespace"] = target_ns
        ctx["tool_used"] = tools_used[0] if tools_used else "get_pod_logs"
        ctx["tools_used"] = tools_used

        if history_text and history_text.strip():
            ctx["deployment_history"] = history_text.strip()
            ctx["version_change_analysis"] = self._analyze_version_changes(
                history_text=history_text,
                pod_name=clean_pod,
            )

        report = self.engine.analyze(entries, context=ctx)
        engine_trace = ctx.get("_engine_trace", {})

        trace_steps.append({
            "step_index": len(trace_steps) + 1,
            "step_type": "diagnostic_rule_evaluation",
            "component": "InvestigationEngine.rules",
            "status": "SUCCESS",
            "duration_ms": engine_trace.get("phase_timings_ms", {}).get("rule_evaluation_ms", 0.0),
            "rules_evaluated_count": engine_trace.get("rules_evaluated_count", len(self.engine.rules)),
            "rules_matched_count": engine_trace.get("rules_matched_count", len(report.findings)),
            "matched_rule_ids": engine_trace.get("matched_rule_ids", [f.id for f in report.findings]),
            "rule_evaluations": engine_trace.get("rule_evaluations", []),
        })

        primary_finding = None
        if report.root_cause and report.root_cause.primary_finding_id:
            primary_finding = next(
                (f for f in report.findings if f.id == report.root_cause.primary_finding_id),
                None,
            )
        if primary_finding is None and report.findings:
            primary_finding = report.findings[0]
        subtype = (
            (primary_finding.metadata.get("subtype") or primary_finding.metadata.get("network_subsystem"))
            if primary_finding
            else None
        )

        trace_steps.append({
            "step_index": len(trace_steps) + 1,
            "step_type": "causal_root_cause_resolution",
            "component": "InvestigationEngine._determine_root_cause",
            "status": "SUCCESS",
            "duration_ms": engine_trace.get("phase_timings_ms", {}).get("root_cause_resolution_ms", 0.0),
            "output_summary": {
                "category": report.root_cause.category.value if report.root_cause else None,
                "subtype": subtype,
                "severity": report.root_cause.severity.value if report.root_cause else None,
                "confidence": report.root_cause.confidence if report.root_cause else None,
                "primary_finding_id": report.root_cause.primary_finding_id if report.root_cause else None,
                "summary": report.root_cause.summary if report.root_cause else None,
                "causal_chain": report.root_cause.causal_chain if report.root_cause else [],
            },
        })

        trace_steps.append({
            "step_index": len(trace_steps) + 1,
            "step_type": "blast_radius_computation",
            "component": "InvestigationEngine._compute_blast_radius",
            "status": "SUCCESS",
            "duration_ms": engine_trace.get("phase_timings_ms", {}).get("blast_radius_computation_ms", 0.0),
            "output_summary": report.blast_radius.model_dump(mode="json"),
        })

        trace_steps.append({
            "step_index": len(trace_steps) + 1,
            "step_type": "remediation_generation",
            "component": "InvestigationEngine._generate_remediations",
            "status": "SUCCESS",
            "duration_ms": engine_trace.get("phase_timings_ms", {}).get("remediation_generation_ms", 0.0),
            "output_summary": {
                "remediation_count": len(report.remediations),
                "kubectl_commands": [r.kubectl_command for r in report.remediations if r.kubectl_command],
            },
        })

        if enable_llm and self.llm_advisor.is_available:
            synthesis = self.llm_advisor.synthesize(
                root_cause=report.root_cause,
                findings=report.findings,
                log_sample=combined_text[:5000],
            )
            report.ai_synthesis = synthesis

        total_duration_ms = round((time.perf_counter() - t_start) * 1000.0, 4)
        completed_at = datetime.now(timezone.utc).isoformat()

        self.last_trace = {
            "investigation_id": report.investigation_id,
            "mode": "pod_investigation",
            "started_at": started_at,
            "completed_at": completed_at,
            "total_duration_ms": total_duration_ms,
            "target": {
                "pod_name": clean_pod,
                "namespace": target_ns,
                "container": container,
            },
            "tools_invoked": tools_used,
            "tool_calls": tool_calls_trace,
            "steps": trace_steps,
            "engine_trace": engine_trace,
            "report": report.to_dict(),
        }

        return report

    def investigate(
        self,
        source: Union[str, Path, TextIO, List[str]],
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        previous: bool = False,
        tail_lines: Optional[int] = None,
        enable_llm: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> InvestigationReport:
        """
        Investigates a Kubernetes Pod by fetching its logs with `get_pod_logs`
        (when given a pod name or natural-language prompt), or analyzes raw log streams.
        """
        import time
        from datetime import datetime, timezone

        t_start = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        if namespace:
            self.parser.default_namespace = namespace

        if isinstance(source, Path):
            source = source.stem

        if isinstance(source, str) and not self._is_raw_log_text(source):
            t_ext_0 = time.perf_counter()
            pod_name, extracted_ns = self._extract_pod_target(source, default_namespace=namespace)
            t_ext_ms = round((time.perf_counter() - t_ext_0) * 1000.0, 4)
            ctx = dict(context) if context else {}
            ctx["_target_extraction_step"] = {
                "step_index": 1,
                "step_type": "target_extraction",
                "component": "KubernetesInvestigationAgent._extract_pod_target",
                "status": "SUCCESS",
                "duration_ms": t_ext_ms,
                "input": {"prompt": source, "default_namespace": namespace},
                "output": {"pod_name": pod_name, "namespace": extracted_ns},
            }
            report = self.investigate_pod(
                pod_name=pod_name,
                namespace=extracted_ns,
                container=container,
                previous=previous,
                tail_lines=tail_lines,
                enable_llm=enable_llm,
                context=ctx,
            )
            if self.last_trace is not None:
                self.last_trace["input_source"] = source
            return report

        # Fallback for in-memory raw log strings, line lists, or streams
        t_parse_0 = time.perf_counter()
        if isinstance(source, list):
            entries = list(self.parser.parse_lines(source))
            raw_text_for_llm = "\n".join(source[:200])
        elif hasattr(source, "read"):
            content = source.read()
            entries = self.parser.parse_text(content)
            raw_text_for_llm = content[:5000]
        else:
            entries = self.parser.parse_text(str(source))
            raw_text_for_llm = str(source)[:5000]
        t_parse_ms = round((time.perf_counter() - t_parse_0) * 1000.0, 4)

        ctx = dict(context) if context else {}
        report = self.engine.analyze(entries, context=ctx)
        engine_trace = ctx.get("_engine_trace", {})

        if enable_llm and self.llm_advisor.is_available:
            synthesis = self.llm_advisor.synthesize(
                root_cause=report.root_cause,
                findings=report.findings,
                log_sample=raw_text_for_llm,
            )
            report.ai_synthesis = synthesis

        total_duration_ms = round((time.perf_counter() - t_start) * 1000.0, 4)
        completed_at = datetime.now(timezone.utc).isoformat()

        level_counts: Dict[str, int] = {}
        components_seen: List[str] = []
        for entry in entries:
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
            if entry.component and entry.component not in components_seen:
                components_seen.append(entry.component)

        primary_finding = None
        if report.root_cause and report.root_cause.primary_finding_id:
            primary_finding = next(
                (f for f in report.findings if f.id == report.root_cause.primary_finding_id),
                None,
            )
        if primary_finding is None and report.findings:
            primary_finding = report.findings[0]
        subtype = (
            (primary_finding.metadata.get("subtype") or primary_finding.metadata.get("network_subsystem"))
            if primary_finding
            else None
        )

        self.last_trace = {
            "investigation_id": report.investigation_id,
            "mode": "raw_log_stream",
            "started_at": started_at,
            "completed_at": completed_at,
            "total_duration_ms": total_duration_ms,
            "tools_invoked": [],
            "tool_calls": [],
            "steps": [
                {
                    "step_index": 1,
                    "step_type": "log_parsing",
                    "component": "LogParser.parse_text",
                    "status": "SUCCESS",
                    "duration_ms": t_parse_ms,
                    "output_summary": {
                        "total_raw_lines": entries[-1].line_number if entries else 0,
                        "parsed_entries_count": len(entries),
                        "level_distribution": level_counts,
                        "detected_components": components_seen,
                        "stack_trace_entries": sum(1 for e in entries if e.is_stack_trace),
                    },
                },
                {
                    "step_index": 2,
                    "step_type": "diagnostic_rule_evaluation",
                    "component": "InvestigationEngine.rules",
                    "status": "SUCCESS",
                    "duration_ms": engine_trace.get("phase_timings_ms", {}).get("rule_evaluation_ms", 0.0),
                    "rules_evaluated_count": engine_trace.get("rules_evaluated_count", len(self.engine.rules)),
                    "rules_matched_count": engine_trace.get("rules_matched_count", len(report.findings)),
                    "matched_rule_ids": engine_trace.get("matched_rule_ids", [f.id for f in report.findings]),
                    "rule_evaluations": engine_trace.get("rule_evaluations", []),
                },
                {
                    "step_index": 3,
                    "step_type": "causal_root_cause_resolution",
                    "component": "InvestigationEngine._determine_root_cause",
                    "status": "SUCCESS",
                    "duration_ms": engine_trace.get("phase_timings_ms", {}).get("root_cause_resolution_ms", 0.0),
                    "output_summary": {
                        "category": report.root_cause.category.value if report.root_cause else None,
                        "subtype": subtype,
                        "severity": report.root_cause.severity.value if report.root_cause else None,
                        "confidence": report.root_cause.confidence if report.root_cause else None,
                        "primary_finding_id": report.root_cause.primary_finding_id if report.root_cause else None,
                        "summary": report.root_cause.summary if report.root_cause else None,
                        "causal_chain": report.root_cause.causal_chain if report.root_cause else [],
                    },
                },
                {
                    "step_index": 4,
                    "step_type": "blast_radius_computation",
                    "component": "InvestigationEngine._compute_blast_radius",
                    "status": "SUCCESS",
                    "duration_ms": engine_trace.get("phase_timings_ms", {}).get("blast_radius_computation_ms", 0.0),
                    "output_summary": report.blast_radius.model_dump(mode="json"),
                },
                {
                    "step_index": 5,
                    "step_type": "remediation_generation",
                    "component": "InvestigationEngine._generate_remediations",
                    "status": "SUCCESS",
                    "duration_ms": engine_trace.get("phase_timings_ms", {}).get("remediation_generation_ms", 0.0),
                    "output_summary": {
                        "remediation_count": len(report.remediations),
                        "kubectl_commands": [r.kubectl_command for r in report.remediations if r.kubectl_command],
                    },
                },
            ],
            "engine_trace": engine_trace,
            "report": report.to_dict(),
        }

        return report

    def investigate_with_trace(
        self,
        source: Union[str, Path, TextIO, List[str]],
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        previous: bool = False,
        tail_lines: Optional[int] = None,
        enable_llm: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[InvestigationReport, Dict[str, Any]]:
        """Runs `investigate(...)` and returns `(report, trace_dict)`."""
        report = self.investigate(
            source=source,
            namespace=namespace,
            container=container,
            previous=previous,
            tail_lines=tail_lines,
            enable_llm=enable_llm,
            context=context,
        )
        return report, (self.last_trace or {})

    def to_markdown(self, report: InvestigationReport) -> str:
        """Renders an InvestigationReport as GitHub-flavored Markdown."""
        return self.renderer.render_markdown(report)

    def to_json(self, report: InvestigationReport) -> str:
        """Renders an InvestigationReport as a JSON string."""
        return self.renderer.render_json(report)

    @staticmethod
    def _analyze_version_changes(history_text: str, pod_name: str = "") -> Dict[str, Any]:
        """
        Parses deployment rollout history or pod description from `get_deployment_history`
        to detect recent pod version or container image changes.
        """
        deploy_match = re.search(
            r"deployment(?:\.apps|\.extensions)?/([a-zA-Z0-9._-]+)",
            history_text,
            re.IGNORECASE,
        )
        deployment_name = deploy_match.group(1) if deploy_match else None
        if not deployment_name and pod_name:
            hash_match = re.match(
                r"^([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)-[a-z0-9]{5,10}-[a-z0-9]{4,6}$",
                pod_name,
                re.IGNORECASE,
            )
            if hash_match:
                deployment_name = hash_match.group(1)

        revisions: List[int] = []
        change_causes: Dict[int, str] = {}
        if deploy_match or "change-cause" in history_text.lower():
            for rev_str, cause in re.findall(r"^\s*(\d+)\s+(.+?)\s*$", history_text, re.MULTILINE):
                rev_num = int(rev_str)
                if rev_num not in revisions:
                    revisions.append(rev_num)
                change_causes[rev_num] = cause.strip()

        revision_images: Dict[int, str] = {}
        for block_match in re.finditer(
            r"deployment(?:\.apps|\.extensions)?/[a-zA-Z0-9._-]+\s+with\s+revision\s+#(\d+)(.*?)(?=deployment(?:\.apps|\.extensions)?/|\Z)",
            history_text,
            re.DOTALL | re.IGNORECASE,
        ):
            rev_num = int(block_match.group(1))
            if rev_num not in revisions:
                revisions.append(rev_num)
            block_body = block_match.group(2)
            img_match = re.search(r"Image:\s*(\S+)", block_body, re.IGNORECASE)
            if img_match:
                revision_images[rev_num] = img_match.group(1).strip()

        # Also check CHANGE-CAUSE strings for image versions (e.g. 'nginx=nginx:1.32.7')
        for rev_num, cause in change_causes.items():
            if rev_num not in revision_images and cause.lower() != "<none>":
                img_in_cause = re.search(
                    r"(?:=|image[:\s]+)([a-zA-Z0-9._/-]+:[a-zA-Z0-9._-]+)",
                    cause,
                    re.IGNORECASE,
                )
                if img_in_cause:
                    revision_images[rev_num] = img_in_cause.group(1).strip()

        revisions.sort()

        if len(revisions) >= 2:
            prev_rev, curr_rev = revisions[-2], revisions[-1]
            prev_img = revision_images.get(prev_rev)
            curr_img = revision_images.get(curr_rev)
            if prev_img and curr_img:
                version_changed = prev_img != curr_img
                if version_changed:
                    summary = (
                        f"Recent deployment rollout (revision #{prev_rev} -> #{curr_rev}) "
                        f"changed pod image version from '{prev_img}' to '{curr_img}'."
                    )
                else:
                    summary = (
                        f"Recent deployment rollout (revision #{prev_rev} -> #{curr_rev}) "
                        f"retained pod image '{curr_img}'."
                    )
            else:
                version_changed = True
                curr_cause = change_causes.get(curr_rev, "<none>")
                detail = curr_img or (curr_cause if curr_cause.lower() != "<none>" else "updated pod template")
                summary = (
                    f"Recent deployment rollout detected (revision #{prev_rev} -> #{curr_rev}, "
                    f"change: '{detail}')."
                )
            return {
                "deployment_name": deployment_name,
                "revisions": revisions,
                "previous_revision": prev_rev,
                "current_revision": curr_rev,
                "previous_version": prev_img,
                "current_version": curr_img,
                "version_changed": version_changed,
                "summary": summary,
            }

        if len(revisions) == 1:
            curr_rev = revisions[0]
            curr_img = revision_images.get(curr_rev)
            if not curr_img:
                img_match = re.search(r"Image:\s*(\S+)", history_text, re.IGNORECASE)
                curr_img = img_match.group(1).strip() if img_match else None
            summary = (
                f"Deployment '{deployment_name or pod_name}' is on revision #{curr_rev}"
                + (f" with image '{curr_img}' (no recent version change)." if curr_img else " (no recent version change).")
            )
            return {
                "deployment_name": deployment_name,
                "revisions": revisions,
                "previous_revision": None,
                "current_revision": curr_rev,
                "previous_version": None,
                "current_version": curr_img,
                "version_changed": False,
                "summary": summary,
            }

        # Standalone pod fallback
        img_match = re.search(r"Image:\s*(\S+)", history_text, re.IGNORECASE)
        curr_img = img_match.group(1).strip() if img_match else None
        summary = (
            f"Standalone pod running image '{curr_img}' (no deployment rollout history)."
            if curr_img
            else None
        )
        return {
            "deployment_name": None,
            "revisions": [],
            "previous_revision": None,
            "current_revision": None,
            "previous_version": None,
            "current_version": curr_img,
            "version_changed": False,
            "summary": summary,
        }

    @staticmethod
    def _is_raw_log_text(source: str) -> bool:
        """Determines whether a string is already raw log lines vs a pod name / prompt."""
        stripped = source.strip()
        if "\n" in stripped:
            return True
        if re.search(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}", stripped):
            return True
        if stripped.startswith("{") and stripped.endswith("}"):
            return True
        if re.match(r"^[IWEF]\d{4}\s+\d{2}:\d{2}:\d{2}", stripped):
            return True
        if re.match(r"^\s*(?:Normal|Warning|Error)\s+[A-Za-z0-9_]+\s+\S+\s+\S+\s+", stripped):
            return True
        if re.match(r"^\s*\S+\s+(?:Normal|Warning|Error)\s+[A-Za-z0-9_]+\s+\S+\s+", stripped):
            return True
        return False

    @staticmethod
    def _extract_pod_target(
        source: str,
        default_namespace: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Extracts `(pod_name, namespace)` from a direct pod identifier or natural-language prompt.
        """
        cleaned = source.strip()
        if not cleaned:
            raise ValueError("No Kubernetes pod name or prompt provided.")

        target_ns = default_namespace or "default"

        def _normalize_candidate(cand: str) -> str:
            cand = cand.strip().strip("\"'`.,;:!?()[]{}")
            # If a path or .log filename was passed, extract the pod name stem
            if "/" in cand or "\\" in cand:
                base = os.path.basename(cand.replace("\\", "/"))
                if any(base.lower().endswith(ext) for ext in (".log", ".txt", ".json", ".yaml", ".yml")):
                    cand = os.path.splitext(base)[0]
                    if cand.endswith("-pod"):
                        cand = cand[:-4]
                    return cand
            for ext in (".log", ".txt", ".json", ".yaml", ".yml"):
                if cand.lower().endswith(ext) and len(cand) > len(ext):
                    cand = cand[: -len(ext)]
            return cand

        # Case 1: Single token (e.g. 'oom-test', 'nginx', 'pod/oom-test', 'default/oom-test')
        if " " not in cleaned and "\t" not in cleaned:
            token = _normalize_candidate(cleaned)
            if "/" in token:
                prefix, remainder = token.split("/", 1)
                if prefix.lower() in ("pod", "pods"):
                    return remainder, target_ns
                return remainder, (default_namespace or prefix)
            return token, target_ns

        # Case 2: Multi-word natural-language prompt
        # 2a. Check for explicit namespace in prompt if default_namespace was not explicitly passed
        if not default_namespace:
            ns_match = re.search(
                r"\b(?:in\s+namespace|namespace[:=\s]+|-n\s+)['\"`]?([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)['\"`]?\b",
                cleaned,
                re.IGNORECASE,
            ) or re.search(
                r"\bin\s+(?:the\s+)?['\"`]?([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)['\"`]?\s+namespace\b",
                cleaned,
                re.IGNORECASE,
            )
            if ns_match:
                cand_ns = ns_match.group(1).lower()
                if cand_ns not in NAMESPACE_STOP_WORDS:
                    target_ns = cand_ns

        # 2b. Check for explicit 'pod/<name>' or '<ns>/<name>' (not a Windows/Unix file path)
        slash_match = re.search(
            r"(?<![:\\/])\b([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)/([a-z0-9](?:[-a-z0-9.]*[a-z0-9])?)\b(?![\\/])",
            cleaned,
            re.IGNORECASE,
        )
        if slash_match:
            prefix, remainder = slash_match.group(1), _normalize_candidate(slash_match.group(2))
            if prefix.lower() in ("pod", "pods"):
                return remainder, target_ns
            if prefix.lower() not in ("http", "https", "var", "tmp", "usr", "etc", "home"):
                return remainder, (default_namespace or prefix)

        # 2c. Explicit 'pod <name>' or 'pod named <name>'
        for m in re.finditer(
            r"\bpods?(?:\s+named|\s+called)?[:=\s]+['\"`]?([a-zA-Z0-9](?:[-_a-zA-Z0-9.]*[a-zA-Z0-9])?)['\"`]?",
            cleaned,
            re.IGNORECASE,
        ):
            cand = _normalize_candidate(m.group(1))
            if cand and cand.lower() not in PROMPT_STOP_WORDS and cand.lower() != target_ns:
                return cand, target_ns

        # 2d. Explicit '<name> pod'
        for m in re.finditer(
            r"['\"`]?([a-zA-Z0-9](?:[-_a-zA-Z0-9.]*[a-zA-Z0-9])?)['\"`]?\s+pods?\b",
            cleaned,
            re.IGNORECASE,
        ):
            cand = _normalize_candidate(m.group(1))
            if cand and cand.lower() not in PROMPT_STOP_WORDS and cand.lower() != target_ns:
                return cand, target_ns

        # 2e. Prepositional / action target e.g. 'failure for <name>', 'of <name>', 'from <path_or_name>'
        for m in re.finditer(
            r"\b(?:for|of|on|from|investigate|check|analyze|debug)\s+(?:the\s+)?(?:pods?\s+)?([^\s\"'`,;!?]+)",
            cleaned,
            re.IGNORECASE,
        ):
            cand = _normalize_candidate(m.group(1))
            if cand and cand.lower() not in PROMPT_STOP_WORDS and cand.lower() != target_ns:
                return cand, target_ns

        # 2f. Quoted identifier anywhere in the prompt
        for m in re.finditer(r"['\"`]([a-zA-Z0-9](?:[-_a-zA-Z0-9.]*[a-zA-Z0-9])?)['\"`]", cleaned):
            cand = _normalize_candidate(m.group(1))
            if cand and cand.lower() not in PROMPT_STOP_WORDS and cand.lower() != target_ns:
                return cand, target_ns

        # 2g. Hyphenated Kubernetes resource identifier (e.g. 'oom-test', 'my-app-7f89')
        for m in re.finditer(r"\b([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+)\b", cleaned):
            cand = _normalize_candidate(m.group(1))
            if cand and cand.lower() not in PROMPT_STOP_WORDS and cand.lower() != target_ns:
                return cand, target_ns

        # 2h. Any remaining non-stopword token
        for raw_token in cleaned.split():
            cand = _normalize_candidate(raw_token)
            if (
                cand
                and re.match(r"^[a-zA-Z0-9](?:[-a-zA-Z0-9.]*[a-zA-Z0-9])?$", cand)
                and cand.lower() not in PROMPT_STOP_WORDS
                and cand.lower() != target_ns
            ):
                return cand, target_ns

        raise ValueError(f"Could not determine a Kubernetes Pod name from input: '{source}'")
