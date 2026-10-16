"""
Multi-format reporting engine for Kubernetes Investigation Agent.
Supports Rich Terminal UI, Markdown Incident Post-Mortem, and Structured JSON exports.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.tree import Tree
except ImportError:  # pragma: no cover
    Console = None  # type: ignore[assignment,misc]
    Panel = None  # type: ignore[assignment,misc]
    Table = None  # type: ignore[assignment,misc]
    Text = None  # type: ignore[assignment,misc]
    Syntax = None  # type: ignore[assignment,misc]
    Tree = None  # type: ignore[assignment,misc]

from k8s_investigate.models import InvestigationReport, Severity


def _supports_unicode() -> bool:
    try:
        encoding = getattr(sys.stdout, "encoding", "") or ""
        return "utf" in encoding.lower()
    except Exception:
        return False


SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "bold dark_orange",
    Severity.MEDIUM: "bold yellow",
    Severity.LOW: "bold blue",
    Severity.INFO: "bold green",
}

SEVERITY_EMOJIS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "🟢",
}


class ReportRenderer:
    """Renders investigation reports in Terminal (Rich), Markdown, or JSON formats."""

    def __init__(self, console: Optional[Any] = None):
        self.console = console or (Console() if Console is not None else None)

    def render_console(self, report: InvestigationReport) -> None:
        """Displays rich colorized terminal dashboard of the investigation."""
        use_unicode = _supports_unicode()

        # 1. Header Panel
        status_color = "red" if "CRITICAL" in report.overall_status else "yellow" if "HIGH" in report.overall_status else "green"
        header_text = Text()
        header_text.append(f"Investigation ID: {report.investigation_id}\n", style="bold cyan")
        header_text.append(f"Status: {report.overall_status}  |  Processed {report.total_log_lines} lines ({report.parsed_entries} entries) in {report.execution_time_seconds}s\n", style=status_color)
        
        hdr_title = "🔍 [bold]Kubernetes Incident Investigation Report[/bold]" if use_unicode else "[INVESTIGATION] [bold]Kubernetes Incident Investigation Report[/bold]"
        self.console.print(Panel(header_text, title=hdr_title, border_style="cyan"))

        # 2. Executive Root Cause Analysis (RCA) Panel
        if report.root_cause:
            rc = report.root_cause
            rc_color = SEVERITY_COLORS.get(rc.severity, "white")
            rc_content = Text()
            rc_content.append(f"Category: {rc.category.value}\n", style="bold")
            rc_content.append(f"Confidence: {int(rc.confidence * 100)}%\n", style="cyan")
            rc_content.append(f"Summary: {rc.summary}\n\n", style=rc_color)

            if rc.causal_chain:
                rc_content.append("Causal Chain:\n", style="bold underline")
                for i, step in enumerate(rc.causal_chain, 1):
                    rc_content.append(f"  {i}. {step}\n", style="white")

            rc_title = f"⚡ [bold]Root Cause Analysis (Severity: {rc.severity.value})[/bold]" if use_unicode else f"[ROOT CAUSE] [bold]Root Cause Analysis (Severity: {rc.severity.value})[/bold]"
            self.console.print(Panel(rc_content, title=rc_title, border_style="red" if rc.severity == Severity.CRITICAL else "orange3"))
        else:
            self.console.print(Panel("[green]No abnormal failure patterns detected. Workload appears healthy or logs are inconclusive.[/green]", title="Status"))

        # 3. Blast Radius Table
        if report.blast_radius.pods_affected or report.blast_radius.namespaces_affected:
            br_title = "🎯 Blast Radius & Impact Scope" if use_unicode else "[IMPACT] Blast Radius & Impact Scope"
            br_table = Table(title=br_title, border_style="dim")
            br_table.add_column("Affected Pods", style="cyan")
            br_table.add_column("Namespaces", style="magenta")
            br_table.add_column("Containers", style="yellow")
            if report.blast_radius.nodes_affected:
                br_table.add_column("Nodes", style="blue")
            br_table.add_column("Estimated Service Impact", style="bold red")

            row_data = [
                ", ".join(report.blast_radius.pods_affected) or "N/A",
                ", ".join(report.blast_radius.namespaces_affected) or "default",
                ", ".join(report.blast_radius.containers_affected) or "N/A",
            ]
            if report.blast_radius.nodes_affected:
                row_data.append(", ".join(report.blast_radius.nodes_affected))
            row_data.append(report.blast_radius.estimated_service_impact)

            br_table.add_row(*row_data)
            self.console.print(br_table)
            self.console.print()

        # 4. Detected Findings Table
        if report.findings:
            f_title = "📋 Detected Incident Findings" if use_unicode else "[FINDINGS] Detected Incident Findings"
            f_table = Table(title=f_title, border_style="bright_blue")
            f_table.add_column("Severity", justify="center", width=12)
            f_table.add_column("Category", style="cyan", width=22)
            f_table.add_column("Finding Title", style="bold white")
            f_table.add_column("Confidence", justify="right", width=12)
            f_table.add_column("Evidence Count", justify="center", width=14)

            for f in report.findings:
                sev_style = SEVERITY_COLORS.get(f.severity, "white")
                sev_label = f"{SEVERITY_EMOJIS.get(f.severity, '')} {f.severity.value}" if use_unicode else f"[{f.severity.value}]"
                f_table.add_row(
                    Text(sev_label, style=sev_style),
                    f.category.value,
                    f.title,
                    f"{int(f.confidence * 100)}%",
                    str(len(f.evidence)),
                )
            self.console.print(f_table)
            self.console.print()

        # 5. Chronological Incident Timeline
        if report.timeline:
            tl_header = "⏱️  [bold]Chronological Incident Timeline[/bold]" if use_unicode else "[TIMELINE] [bold]Chronological Incident Timeline[/bold]"
            tl_tree = Tree(tl_header)
            for event in report.timeline:
                ts_str = event.relative_time_str
                sev_color = SEVERITY_COLORS.get(event.severity, "white")
                res_info = f" [{event.resource}]" if event.resource else ""
                node_label = f"[{sev_color}]{ts_str}[/{sev_color}] (Line {event.line_number}){res_info}: [bold]{event.event_type}[/bold] - {event.summary}"
                tl_tree.add(node_label)
            self.console.print(tl_tree)
            self.console.print()

        # 6. Supporting Evidence Log Extracts
        if report.findings:
            ev_header = "🔬 [bold underline]Supporting Evidence (Exact Log Extracts)[/bold underline]\n" if use_unicode else "[EVIDENCE] [bold underline]Supporting Evidence (Exact Log Extracts)[/bold underline]\n"
            self.console.print(ev_header)
            for f in report.findings:
                for idx, ev in enumerate(f.evidence, 1):
                    ev_title = f"Finding: {f.title} | Lines {ev.start_line}-{ev.end_line}"
                    if ev.timestamp:
                        ev_title += f" ({ev.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
                    
                    raw_text = "\n".join(ev.raw_lines)
                    syntax = Syntax(raw_text, "text", theme="monokai", line_numbers=False)
                    self.console.print(Panel(
                        syntax,
                        title=ev_title,
                        subtitle=f"Reason: {ev.highlighted_reason}",
                        border_style="yellow" if f.severity in [Severity.HIGH, Severity.CRITICAL] else "dim",
                    ))

        # 7. Actionable Remediation Plan
        if report.remediations:
            rem_header = "🛠️  [bold underline]Actionable Remediation & Mitigation Plan[/bold underline]\n" if use_unicode else "[REMEDIATION] [bold underline]Actionable Remediation & Mitigation Plan[/bold underline]\n"
            self.console.print(rem_header)
            for i, rem in enumerate(report.remediations, 1):
                type_label = rem.action_type.replace("_", " ").upper()
                rem_text = Text()
                rem_text.append(f"[{type_label}] {rem.description}\n", style="bold cyan")
                if rem.explanation:
                    rem_text.append(f"Explanation: {rem.explanation}\n", style="dim")
                
                self.console.print(rem_text)
                if rem.kubectl_command:
                    self.console.print(Syntax(rem.kubectl_command, "bash", theme="monokai", background_color="default"))
                if rem.yaml_patch:
                    self.console.print(Syntax(rem.yaml_patch, "yaml", theme="monokai", background_color="default"))
                self.console.print()

        # 8. AI Synthesis (if available)
        if report.ai_synthesis:
            ai_title = "🤖 [bold]AI Expert Review & Architecture Advice[/bold]" if use_unicode else "[AI] [bold]AI Expert Review & Architecture Advice[/bold]"
            self.console.print(Panel(
                report.ai_synthesis,
                title=ai_title,
                border_style="magenta",
            ))

    def render_markdown(self, report: InvestigationReport) -> str:
        """Generates a professional Markdown Post-Mortem incident report."""
        lines = []
        lines.append(f"# 🛡️ Kubernetes Incident Investigation Report")
        lines.append(f"**Investigation ID:** `{report.investigation_id}`  ")
        lines.append(f"**Generated At:** `{report.generated_at.strftime('%Y-%m-%d %H:%M:%SZ')}`  ")
        lines.append(f"**Overall Status:** **`{report.overall_status}`**  ")
        lines.append(f"**Log Processing:** `{report.total_log_lines}` lines parsed ({report.parsed_entries} entries) in `{report.execution_time_seconds}s`\n")
        lines.append("---\n")

        # Root Cause Analysis
        lines.append("## 1. Executive Summary & Root Cause Analysis (RCA)")
        if report.root_cause:
            rc = report.root_cause
            lines.append(f"| Property | Value |")
            lines.append(f"| :--- | :--- |")
            lines.append(f"| **Primary Root Cause** | `{rc.category.value}` |")
            lines.append(f"| **Severity** | **{rc.severity.value}** |")
            lines.append(f"| **Confidence** | **{int(rc.confidence * 100)}%** |")
            lines.append(f"| **Summary** | {rc.summary} |\n")

            if rc.causal_chain:
                lines.append("### Causal Incident Chain")
                for i, step in enumerate(rc.causal_chain, 1):
                    lines.append(f"{i}. {step}")
                lines.append("")

            if rc.contributing_factors:
                lines.append("### Contributing Factors")
                for factor in rc.contributing_factors:
                    lines.append(f"- {factor}")
                lines.append("")
        else:
            lines.append("> No abnormal failure patterns detected. The analyzed workload logs indicate normal operations.\n")

        # Blast Radius
        lines.append("## 2. Blast Radius & Impact Assessment")
        lines.append(f"- **Impacted Pods:** {', '.join(f'`{p}`' for p in report.blast_radius.pods_affected) or 'None'}")
        lines.append(f"- **Impacted Containers:** {', '.join(f'`{c}`' for c in report.blast_radius.containers_affected) or 'None'}")
        lines.append(f"- **Impacted Namespaces:** {', '.join(f'`{n}`' for n in report.blast_radius.namespaces_affected) or 'default'}")
        if report.blast_radius.nodes_affected:
            lines.append(f"- **Impacted Nodes:** {', '.join(f'`{n}`' for n in report.blast_radius.nodes_affected)}")
        lines.append(f"- **Service Impact:** {report.blast_radius.estimated_service_impact}\n")

        # Findings Summary Table
        lines.append("## 3. Detected Findings & Anomalies")
        if report.findings:
            lines.append("| ID | Severity | Category | Title | Confidence | Evidence Snippets |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for f in report.findings:
                lines.append(f"| `{f.id}` | **{f.severity.value}** | `{f.category.value}` | {f.title} | {int(f.confidence * 100)}% | {len(f.evidence)} |")
            lines.append("")
        else:
            lines.append("No findings recorded.\n")

        # Timeline
        lines.append("## 4. Chronological Incident Timeline")
        if report.timeline:
            lines.append("| Timestamp / Line | Severity | Event Type | Resource | Summary |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for ev in report.timeline:
                res = f"`{ev.resource}`" if ev.resource else "-"
                lines.append(f"| `{ev.relative_time_str}` | **{ev.severity.value}** | `{ev.event_type}` | {res} | {ev.summary} |")
            lines.append("")
        else:
            lines.append("No timeline events generated.\n")

        # Supporting Evidence
        lines.append("## 5. Supporting Evidence (Log Extracts)")
        if report.findings:
            for f in report.findings:
                lines.append(f"### Finding: {f.title} (`{f.category.value}`)")
                lines.append(f"**Description:** {f.description}\n")
                
                for idx, ev in enumerate(f.evidence, 1):
                    ts_info = f" (Timestamp: {ev.timestamp.isoformat()})" if ev.timestamp else ""
                    lines.append(f"#### Evidence #{idx}: Lines {ev.start_line} - {ev.end_line}{ts_info}")
                    lines.append(f"> **Reason:** {ev.highlighted_reason}\n")
                    if ev.extracted_params:
                        lines.append("**Extracted Parameters:**")
                        for k, v in ev.extracted_params.items():
                            lines.append(f"- `{k}`: `{v}`")
                        lines.append("")

                    lines.append("```log")
                    for line in ev.raw_lines:
                        lines.append(line)
                    lines.append("```\n")
        else:
            lines.append("No evidence to display.\n")

        # Remediation
        lines.append("## 6. Actionable Remediation & Mitigation Plan")
        if report.remediations:
            for idx, rem in enumerate(report.remediations, 1):
                type_badge = rem.action_type.replace("_", " ").title()
                lines.append(f"### {idx}. [{type_badge}] {rem.description}")
                if rem.explanation:
                    lines.append(f"{rem.explanation}\n")
                if rem.kubectl_command:
                    lines.append("```bash")
                    lines.append(rem.kubectl_command)
                    lines.append("```\n")
                if rem.yaml_patch:
                    lines.append("```yaml")
                    lines.append(rem.yaml_patch)
                    lines.append("```\n")
        else:
            lines.append("No immediate actions required.\n")

        # AI Synthesis
        if report.ai_synthesis:
            lines.append("## 7. AI Advisory & Deep Technical Breakdown")
            lines.append(report.ai_synthesis)
            lines.append("")

        return "\n".join(lines)

    def render_json(self, report: InvestigationReport) -> str:
        """Serializes report into JSON string."""
        return json.dumps(report.to_dict(), indent=2)
