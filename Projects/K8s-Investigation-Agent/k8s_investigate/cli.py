"""
Command-Line Interface (CLI) for Kubernetes Investigation Agent.
Uses `get_pod_logs` and `get_pod_events` tools to fetch logs and events of a specific Kubernetes Pod
and perform root cause analysis.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console

from k8s_investigate.agent import KubernetesInvestigationAgent
from k8s_investigate.reporter import ReportRenderer

# Ensure standard output can handle UTF-8 on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@click.command(name="k8s-investigate")
@click.argument("source", nargs=-1, required=False, type=str)
@click.option(
    "--pod", "-p", "pod_name",
    type=str,
    default=None,
    help="Name of the Kubernetes Pod to fetch logs and events from using get_pod_logs and get_pod_events.",
)
@click.option(
    "--namespace", "-n",
    type=str,
    default=None,
    help="Kubernetes namespace of the pod (default: 'default').",
)
@click.option(
    "--container", "-c",
    type=str,
    default=None,
    help="Optional specific container name within the pod.",
)
@click.option(
    "--previous",
    is_flag=True,
    default=False,
    help="Fetch logs from the previous terminated container instance.",
)
@click.option(
    "--tail", "tail_lines",
    type=int,
    default=None,
    help="Number of most recent log lines to fetch from the pod.",
)
@click.option(
    "--output", "-o", "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to save report output (supports .md, .markdown, .json, .txt).",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["terminal", "markdown", "json"], case_sensitive=False),
    default="terminal",
    help="Output presentation format.",
)
@click.option(
    "--llm/--no-llm",
    default=False,
    help="Enable optional LLM AI advisor synthesis if API key is configured.",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress terminal output (useful when exporting directly to a file).",
)
def main(
    source: tuple[str, ...],
    pod_name: Optional[str],
    namespace: Optional[str],
    container: Optional[str],
    previous: bool,
    tail_lines: Optional[int],
    output_path: Optional[Path],
    output_format: str,
    llm: bool,
    quiet: bool,
):
    """
    Kubernetes Investigation Agent CLI.
    Uses `get_pod_logs` and `get_pod_events` tools to fetch logs and events of a specific Kubernetes Pod
    and perform root cause analysis.

    Examples:
      k8s-investigate oom-test
      k8s-investigate --pod nginx --namespace default
      agent-cli run "Investigate the pod failure for oom-test"
    """
    console = Console()
    agent = KubernetesInvestigationAgent()
    renderer = ReportRenderer(console=console)

    # Normalize positional source arguments (support optional 'run' subcommand prefix)
    source_args = list(source) if source else []
    if len(source_args) > 1 and source_args[0].lower() == "run":
        source_args = source_args[1:]
    source_str = " ".join(source_args).strip() if source_args else None

    target_input = pod_name or source_str
    if not target_input:
        console.print(
            "[bold red]Error:[/bold red] No Kubernetes Pod specified. "
            "Provide a pod name or prompt (e.g., [bold]k8s-investigate <pod-name>[/bold] or [bold]--pod <pod-name>[/bold])."
        )
        console.print("Run [bold cyan]k8s-investigate --help[/bold cyan] for usage instructions.")
        sys.exit(1)

    try:
        if not quiet and output_format == "terminal":
            with console.status(
                "[bold green]Fetching pod logs & events via get_pod_logs and get_pod_events tools..."
            ):
                report = agent.investigate(
                    source=target_input,
                    namespace=namespace,
                    container=container,
                    previous=previous,
                    tail_lines=tail_lines,
                    enable_llm=llm,
                )
        else:
            report = agent.investigate(
                source=target_input,
                namespace=namespace,
                container=container,
                previous=previous,
                tail_lines=tail_lines,
                enable_llm=llm,
            )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)

    # Format auto-detection based on file extension if output_path is provided
    if output_path and output_format == "terminal":
        ext = output_path.suffix.lower()
        if ext in [".md", ".markdown"]:
            output_format = "markdown"
        elif ext in [".json"]:
            output_format = "json"

    # Display / Export
    if output_format == "terminal" and not quiet:
        renderer.render_console(report)
    elif output_format == "markdown":
        md_content = renderer.render_markdown(report)
        if not quiet:
            console.print(md_content)
    elif output_format == "json":
        json_content = renderer.render_json(report)
        if not quiet:
            console.print(json_content)

    # Write output to file if requested
    if output_path:
        if output_format == "json" or output_path.suffix.lower() == ".json":
            file_content = renderer.render_json(report)
        else:
            file_content = renderer.render_markdown(report)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        console.print(f"[bold green]✓[/bold green] Detailed investigation report saved to: [cyan]{output_path}[/cyan]")


if __name__ == "__main__":
    main()
