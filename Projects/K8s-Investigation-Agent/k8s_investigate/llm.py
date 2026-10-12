"""
Optional LLM Enrichment Layer.
Leverages Google Gemini (via google-genai) or OpenAI if API keys are configured in the environment,
providing deep contextual synthesis, post-mortem writeups, and architectural recommendations.
If no API key is provided, gracefully operates in 100% autonomous deterministic mode.
"""

from __future__ import annotations

import os
from typing import Optional

from k8s_investigate.models import Finding, RootCause


class LLMAdvisor:
    """Provides optional AI synthesis over deterministic investigation findings."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def synthesize(
        self,
        root_cause: Optional[RootCause],
        findings: list[Finding],
        log_sample: str,
    ) -> Optional[str]:
        """Synthesizes high-level executive insights using Gemini if available."""
        if not self.is_available or not self.client:
            return None

        findings_summary = "\n".join(
            f"- [{f.category.value}] {f.title}: {f.description}" for f in findings
        )
        rc_text = root_cause.summary if root_cause else "Undetermined"

        prompt = f"""You are a Principal Kubernetes Reliability Engineer investigating a production incident.
Based on the following extracted diagnostic evidence, provide a concise incident review with:
1. Executive Assessment
2. Deep Technical Breakdown
3. Architecture-level Prevention Recommendations

Root Cause Identified:
{rc_text}

Findings Detected:
{findings_summary}

Sample Log Snippets:
{log_sample[:3000]}

Keep the response structured and engineering-focused.
"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except Exception:
            return None
