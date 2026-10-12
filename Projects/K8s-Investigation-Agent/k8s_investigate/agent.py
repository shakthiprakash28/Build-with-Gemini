"""
Main Kubernetes Investigation Agent.
Provides the primary programmatic interface for investigating Kubernetes logs from files,
directories, stdin streams, or raw strings.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from k8s_investigate.engine import InvestigationEngine
from k8s_investigate.llm import LLMAdvisor
from k8s_investigate.models import InvestigationReport, LogEntry
from k8s_investigate.parser import LogParser
from k8s_investigate.reporter import ReportRenderer


class KubernetesInvestigationAgent:
    """
    Autonomous Kubernetes Investigation Agent.
    Ingests logs, identifies failure anomalies, computes causal root causes,
    extracts supporting evidence, and provides actionable remediation guidance.
    """

    def __init__(
        self,
        engine: Optional[InvestigationEngine] = None,
        parser: Optional[LogParser] = None,
        llm_advisor: Optional[LLMAdvisor] = None,
        renderer: Optional[ReportRenderer] = None,
    ):
        self.parser = parser or LogParser()
        self.engine = engine or InvestigationEngine()
        self.llm_advisor = llm_advisor or LLMAdvisor()
        self.renderer = renderer or ReportRenderer()

    def investigate(
        self,
        source: Union[str, Path, TextIO, List[str]],
        namespace: Optional[str] = None,
        enable_llm: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> InvestigationReport:
        """
        Investigates the provided log input (raw string, file path, stream, or line list).
        """
        if namespace:
            self.parser.default_namespace = namespace

        raw_text_for_llm = ""

        # Normalize potential git-bash/msys path on Windows, e.g. /d/... -> D:/...
        resolved_path: Optional[Path] = None
        if isinstance(source, Path):
            resolved_path = source
        elif isinstance(source, str):
            cleaned = source.strip()
            if sys.platform == "win32":
                m = re.match(r"^/([a-zA-Z])/(.*)$", cleaned)
                if m:
                    converted = f"{m.group(1).upper()}:/{m.group(2)}"
                    if os.path.exists(converted):
                        resolved_path = Path(converted)
            if not resolved_path and os.path.exists(cleaned):
                resolved_path = Path(cleaned)

        # Determine source type
        if resolved_path:
            if resolved_path.is_file():
                entries, raw_text_for_llm = self._read_file(resolved_path)
            elif resolved_path.is_dir():
                entries, raw_text_for_llm = self._read_directory(resolved_path)
            else:
                entries = self.parser.parse_text(str(source))
                raw_text_for_llm = str(source)
        elif isinstance(source, list):
            entries = list(self.parser.parse_lines(source))
            raw_text_for_llm = "\n".join(source[:200])
        elif hasattr(source, "read"):
            content = source.read()
            entries = self.parser.parse_text(content)
            raw_text_for_llm = content[:5000]
        else:
            # String of logs
            entries = self.parser.parse_text(str(source))
            raw_text_for_llm = str(source)[:5000]

        # Execute investigation engine
        report = self.engine.analyze(entries, context=context)

        # Optional LLM Advisory synthesis
        if enable_llm and self.llm_advisor.is_available:
            synthesis = self.llm_advisor.synthesize(
                root_cause=report.root_cause,
                findings=report.findings,
                log_sample=raw_text_for_llm,
            )
            report.ai_synthesis = synthesis

        return report

    def _read_file(self, path: Path) -> tuple[List[LogEntry], str]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        entries = self.parser.parse_text(content)
        return entries, content[:5000]

    def _read_directory(self, dir_path: Path) -> tuple[List[LogEntry], str]:
        all_entries: List[LogEntry] = []
        combined_text_sample = []
        line_offset = 0

        # Scan for .log, .txt, .json files
        files = sorted(glob.glob(str(dir_path / "**/*"), recursive=True))
        for file_str in files:
            fpath = Path(file_str)
            if fpath.is_file() and fpath.suffix in [".log", ".txt", ".json", ""]:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    combined_text_sample.append(f"--- File: {fpath.name} ---")
                    combined_text_sample.extend(lines[:20])

                    file_entries = list(self.parser.parse_lines(lines))
                    # Adjust line numbers to be cumulative across directory
                    for e in file_entries:
                        e.line_number += line_offset
                        e.metadata["source_file"] = fpath.name
                    all_entries.extend(file_entries)
                    line_offset += len(lines)
                except Exception:
                    continue

        return all_entries, "\n".join(combined_text_sample[:100])
