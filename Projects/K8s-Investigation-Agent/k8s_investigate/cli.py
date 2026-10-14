"""
Command-Line Interface (CLI) for Kubernetes Investigation Agent.
Supports analyzing files, directories, or piped logs from stdin (e.g., kubectl logs | ...).
"""

from __future__ import annotations

import re
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
    "--file", "-f", "file_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a single Kubernetes log file.",
)
@click.option(
    "--dir", "-d", "dir_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to a directory containing Kubernetes log files.",
)
@click.option(
    "--namespace", "-n",
    type=str,
    default=None,
    help="Default Kubernetes namespace context.",
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
    file_path: Optional[Path],
    dir_path: Optional[Path],
    namespace: Optional[str],
    output_path: Optional[Path],
    output_format: str,
    llm: bool,
    quiet: bool,
):
    """
    Kubernetes Investigation Agent CLI.
    
    Examples:
      k8s-investigate sample_logs/oom_killed_crashloop.log
      k8s-investigate --file /var/log/pods/app.log --output report.md
      kubectl logs my-app-7f89 | k8s-investigate - --output incident.json
    """
    console = Console()
    agent = KubernetesInvestigationAgent()
    renderer = ReportRenderer(console=console)

    # Normalize positional source arguments (support optional 'run' subcommand prefix)
    source_args = list(source) if source else []
    if len(source_args) > 1 and source_args[0].lower() == "run":
        source_args = source_args[1:]
    source_str = " ".join(source_args).strip() if source_args else None

    # Resolve target log source
    input_target = None
    if file_path:
        input_target = file_path
    elif dir_path:
        input_target = dir_path
    elif source_str == "-" or (not source_str and not sys.stdin.isatty()):
        # Read from stdin
        if not quiet:
            console.print("[dim]Reading log stream from stdin...[/dim]")
        input_target = sys.stdin.read()
    elif source_str:
        resolved_src = agent._resolve_source_path(source_str)
        if resolved_src:
            input_target = resolved_src
        else:
            # Source might be a raw string
            input_target = source_str
    else:
        console.print("[bold red]Error:[/bold red] No log input provided. Specify a log file, directory, or pipe logs via stdin.")
        console.print("Run [bold cyan]k8s-investigate --help[/bold cyan] for usage instructions.")
        sys.exit(1)

    # Run investigation
    if not quiet and output_format == "terminal":
        with console.status("[bold green]Investigating Kubernetes logs, extracting evidence & determining root cause..."):
            report = agent.investigate(
                source=input_target,
                namespace=namespace,
                enable_llm=llm,
            )
    else:
        report = agent.investigate(
            source=input_target,
            namespace=namespace,
            enable_llm=llm,
        )

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
