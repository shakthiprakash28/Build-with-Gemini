"""
Multi-format Kubernetes log parser.
Parses raw log files, streaming input, container runtime logs (CRI/containerd/Docker),
Kubernetes event tables, JSON logs, and multi-line application stack traces.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple
from dateutil import parser as date_parser

from k8s_investigate.models import LogEntry


# Common regex patterns for log components
CRI_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\s+"
    r"(?P<stream>stdout|stderr)\s+"
    r"(?P<tag>[FP])\s+"
    r"(?P<message>.*)$"
)

ISO_TIMESTAMP_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
)

K8S_KUBELET_PATTERN = re.compile(
    r"^(?P<severity>[IWEF])(?P<month>\d{2})(?P<day>\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<file>[^:]+:\d+)\]\s+"
    r"(?P<message>.*)$"
)

K8S_EVENT_ROW_PATTERN = re.compile(
    r"^\s*(?P<type>Normal|Warning|Error)\s+"
    r"(?P<reason>[A-Za-z0-9_]+)\s+"
    r"(?P<age>\S+(?:\s+\([^)]+\))?)\s+"
    r"(?P<from>[A-Za-z0-9_\-\.]+)\s+"
    r"(?P<message>.+)$"
)

K8S_GET_EVENTS_PATTERN = re.compile(
    r"^\s*(?P<last_seen>\S+)\s+"
    r"(?P<type>Normal|Warning|Error)\s+"
    r"(?P<reason>[A-Za-z0-9_]+)\s+"
    r"(?P<object>\S+)\s+"
    r"(?P<message>.+)$"
)

LOG_LEVEL_PATTERN = re.compile(
    r"\b(?P<level>FATAL|CRITICAL|ERROR|ERR|WARN|WARNING|INFO|DEBUG|TRACE)\b",
    re.IGNORECASE
)

# Pod patterns: explicit prefix or standard k8s pod naming format
POD_EXPLICIT_PATTERN = re.compile(
    r"\b(?:pod(?:s)?[:/=\s]+|in pod\s+['\"]?|for pod\s+['\"]?|assigned\s+[a-z0-9\-.]+/)([a-z0-9](?:[-_a-z0-9]*[a-z0-9])?)\b",
    re.IGNORECASE,
)
POD_STRUCTURE_PATTERN = re.compile(
    r"\b([a-z0-9]+(?:-[a-z0-9]+)*-[a-z0-9]{5,10}-[a-z0-9]{4,6}(?:_[a-z0-9]+)?)\b|"
    r"\b([a-z0-9]+(?:-[a-z0-9]+)+-\d+)\b",
    re.IGNORECASE,
)

NAMESPACE_PATTERN = re.compile(
    r"\b(?:namespace[:=\s]+|in namespace\s+['\"]?|namespace\s+['\"])([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)\b",
    re.IGNORECASE,
)

CONTAINER_PATTERN = re.compile(
    r"\b(?:container[:=]|in container\s+['\"]?|failed container\s+['\"]?|container\s+['\"])([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)\b|"
    r"\b(?:container\s+)([a-z0-9]+(?:-[a-z0-9]+)+)\b",
    re.IGNORECASE,
)

NODE_PATTERN = re.compile(
    r"\b(?:assigned\s+(?:\S+\s+)?to node\s+|assigned to\s+|to node\s+|attached to\s+|on node\s+|node[:=\s]+)([a-z0-9]+(?:-[a-z0-9]+)+)\b|"
    r"\bassigned\s+[a-z0-9\-.]+/[a-z0-9_\-.]+\s+to\s+([a-z0-9](?:[-.a-z0-9]*[a-z0-9])?)\b",
    re.IGNORECASE,
)

STOP_WORDS = {
    "at", "in", "for", "on", "to", "by", "from", "with", "over", "under", "into",
    "error", "warning", "warn", "info", "debug", "trace", "fatal", "critical",
    "failed", "cluster", "system", "default", "java", "cgroup", "node", "nodes",
    "container", "containers", "pod", "pods", "memory", "cpu", "mount", "volume",
    "secret", "secrets", "service", "services", "killed", "exit", "code", "line",
    "lines", "backoff", "back-off", "stdout", "stderr", "normal", "true", "false",
    "none", "null", "nil", "tcp", "udp", "http", "https", "grpc", "kubelet",
    "scheduler", "controller", "manager", "ingress", "egress", "network", "image",
    "pull", "pulling", "started", "restarting", "created", "killing", "probe",
    "event", "events", "reason", "type", "age", "message", "unhealthy", "healthy",
    "status", "spec", "metadata", "namespace", "ready", "syncing", "skipping",
    "running", "completed", "terminated", "will", "and", "or", "not", "is", "was",
    "sandbox", "condition", "conditions", "state", "phase",
}

STACK_TRACE_START_PATTERN = re.compile(
    r"(?:Traceback \(most recent call last\):|"
    r"Exception in thread .*|"
    r"panic: .*|"
    r"(?:[a-zA-Z0-9_\.]+(?:Exception|Error|Panic)):.*|"
    r"goroutine \d+ \[.*\]:)"
)

STACK_TRACE_LINE_PATTERN = re.compile(
    r"(?:^\s+at\s+.*|"
    r"^\s+File\s+\".*\",\s+line\s+\d+.*|"
    r"^\s+(?:goroutine|\t).*\.go:\d+.*|"
    r"^\s+Caused by:.*|"
    r"^\s+\.\.\. \d+ more)"
)

PYTHON_EXC_TRAILER_PATTERN = re.compile(r"^[a-zA-Z0-9_\.]*(?:Exception|Error|Panic|Fault):\s*.*")

DESCRIBE_NAME_PATTERN = re.compile(r"^Name:\s+([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)\s*$", re.IGNORECASE)
DESCRIBE_NS_PATTERN = re.compile(r"^Namespace:\s+([a-z0-9](?:[-a-z0-9]*[a-z0-9])?)\s*$", re.IGNORECASE)
DESCRIBE_NODE_PATTERN = re.compile(r"^Node:\s+([a-z0-9\-.]+?)(?:/[0-9\.]*)?\s*$", re.IGNORECASE)
DESCRIBE_CONTAINERS_HEADER = re.compile(r"^Containers:\s*$", re.IGNORECASE)
DESCRIBE_CONTAINER_ITEM = re.compile(r"^\s{2}([a-z0-9](?:[-a-z0-9]*[a-z0-9])?):\s*$", re.IGNORECASE)
DESCRIBE_SECTION_HEADER = re.compile(r"^[A-Z][a-zA-Z\s\-]+:\s*$")


class LogParser:
    """Parses raw text and structured log streams into LogEntry models."""

    def __init__(self, default_namespace: Optional[str] = None):
        self.default_namespace = default_namespace

    def parse_text(self, text: str) -> List[LogEntry]:
        """Parses a multi-line string of logs into a list of LogEntry items."""
        lines = text.splitlines()
        return list(self.parse_lines(lines))

    def parse_lines(self, lines: Iterator[str] | List[str]) -> Iterator[LogEntry]:
        """
        Parses an iterable of raw log strings, aggregating multi-line stack traces
        and normalizing metadata.
        """
        current_entry: Optional[LogEntry] = None
        stack_trace_buffer: List[str] = []

        context_pod: Optional[str] = None
        context_namespace: Optional[str] = self.default_namespace
        context_node: Optional[str] = None
        context_container: Optional[str] = None
        in_containers_section: bool = False

        def _apply_context(entry: LogEntry) -> LogEntry:
            if not entry.pod and context_pod:
                entry.pod = context_pod
            elif context_pod and entry.pod and entry.pod.startswith(f"{context_pod}_"):
                entry.pod = context_pod
            if (not entry.namespace or entry.namespace == "default") and context_namespace:
                entry.namespace = context_namespace
            if not entry.node and context_node:
                entry.node = context_node
            if not entry.container and context_container:
                entry.container = context_container
            return entry

        for idx, raw_line in enumerate(lines, start=1):
            line_str = raw_line.rstrip("\r\n")
            if not line_str.strip():
                continue

            # Check describe header patterns
            m_name = DESCRIBE_NAME_PATTERN.match(line_str)
            if m_name and self._is_valid_identifier(m_name.group(1)):
                context_pod = m_name.group(1)

            m_ns = DESCRIBE_NS_PATTERN.match(line_str)
            if m_ns and self._is_valid_identifier(m_ns.group(1)):
                context_namespace = m_ns.group(1)

            m_node = DESCRIBE_NODE_PATTERN.match(line_str)
            if m_node and self._is_valid_identifier(m_node.group(1)):
                context_node = m_node.group(1)

            if DESCRIBE_CONTAINERS_HEADER.match(line_str):
                in_containers_section = True
            elif in_containers_section:
                m_ct = DESCRIBE_CONTAINER_ITEM.match(line_str)
                if m_ct and self._is_valid_identifier(m_ct.group(1)):
                    context_container = m_ct.group(1)
                elif DESCRIBE_SECTION_HEADER.match(line_str):
                    in_containers_section = False

            # Check if this line is a continuation of an ongoing stack trace
            if current_entry and (
                STACK_TRACE_LINE_PATTERN.match(line_str)
                or (stack_trace_buffer and (line_str.startswith(" ") or PYTHON_EXC_TRAILER_PATTERN.match(line_str)))
            ):
                stack_trace_buffer.append(line_str)
                current_entry.is_stack_trace = True
                continue
            
            # If we had a previous entry with buffered stack traces, flush it
            if current_entry and stack_trace_buffer:
                current_entry.message += "\n" + "\n".join(stack_trace_buffer)
                current_entry.raw += "\n" + "\n".join(stack_trace_buffer)
                yield _apply_context(current_entry)
                current_entry = None
                stack_trace_buffer = []
            elif current_entry:
                yield _apply_context(current_entry)
                current_entry = None

            # Check if this line starts a new stack trace while tied to previous error
            if STACK_TRACE_START_PATTERN.search(line_str):
                stack_trace_buffer.append(line_str)
                current_entry = self._parse_single_line(line_str, idx)
                current_entry.is_stack_trace = True
                continue

            # Parse regular line
            parsed = self._parse_single_line(line_str, idx)
            current_entry = parsed

        # Flush the final entry if any
        if current_entry:
            if stack_trace_buffer:
                current_entry.message += "\n" + "\n".join(stack_trace_buffer)
                current_entry.raw += "\n" + "\n".join(stack_trace_buffer)
                current_entry.is_stack_trace = True
            yield _apply_context(current_entry)

    def _parse_single_line(self, line: str, line_number: int) -> LogEntry:
        """Parses an individual line using JSON, CRI, Kubelet, K8s Event, or Plaintext formats."""
        # 1. Try JSON parsing
        stripped = line.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            json_entry = self._try_parse_json(stripped, line_number, line)
            if json_entry:
                return json_entry

        # 2. Try Container CRI format (RFC3339 timestamp stream tag message)
        cri_match = CRI_LOG_PATTERN.match(line)
        if cri_match:
            return self._parse_cri_match(cri_match, line_number, line)

        # 3. Try Kubelet log format (e.g. E1010 00:15:30.123456 ...)
        kubelet_match = K8S_KUBELET_PATTERN.match(line)
        if kubelet_match:
            return self._parse_kubelet_match(kubelet_match, line_number, line)

        # 4. Try Kubernetes describe / event table row
        event_match = K8S_EVENT_ROW_PATTERN.match(line)
        if event_match:
            return self._parse_event_match(event_match, line_number, line)

        get_event_match = K8S_GET_EVENTS_PATTERN.match(line)
        if get_event_match and not line.strip().startswith("LAST SEEN"):
            return self._parse_get_event_match(get_event_match, line_number, line)

        # 5. Generic log format with timestamp and level extraction
        return self._parse_generic_line(line, line_number)

    def _try_parse_json(self, stripped: str, line_number: int, raw_line: str) -> Optional[LogEntry]:
        try:
            data = json.loads(stripped)
            if not isinstance(data, dict):
                return None

            # Extract message
            message = ""
            for key in ["message", "msg", "log", "text", "error", "err"]:
                if key in data and data[key]:
                    message = str(data[key])
                    break
            if not message:
                message = stripped

            # Extract timestamp
            timestamp = None
            for key in ["timestamp", "time", "ts", "@timestamp", "date"]:
                if key in data and data[key]:
                    timestamp = self._parse_timestamp(str(data[key]))
                    if timestamp:
                        break

            # Extract level
            level = "INFO"
            for key in ["level", "severity", "lvl", "log_level"]:
                if key in data and data[key]:
                    level = self._normalize_level(str(data[key]))
                    break

            # Extract metadata
            stream = data.get("stream")
            pod = data.get("pod") or data.get("pod_name") or data.get("kubernetes", {}).get("pod_name")
            namespace = data.get("namespace") or data.get("kubernetes", {}).get("namespace_name") or self.default_namespace
            container = data.get("container") or data.get("container_name") or data.get("kubernetes", {}).get("container_name")
            node = data.get("node") or data.get("node_name") or data.get("kubernetes", {}).get("node_name")
            component = data.get("component") or data.get("logger") or data.get("app")

            return LogEntry(
                line_number=line_number,
                raw=raw_line,
                timestamp=timestamp,
                level=level,
                stream=stream,
                pod=pod,
                namespace=namespace,
                container=container,
                node=node,
                component=component,
                message=message,
                metadata=data,
            )
        except Exception:
            return None

    def _parse_cri_match(self, match: re.Match, line_number: int, raw_line: str) -> LogEntry:
        ts_str = match.group("timestamp")
        stream = match.group("stream")
        msg = match.group("message")
        timestamp = self._parse_timestamp(ts_str)

        level = self._detect_level(msg)
        if stream == "stderr" and level == "INFO":
            # stderr could be error or warning
            level = "WARN"

        pod, namespace, container, node = self._extract_k8s_identifiers(msg)

        return LogEntry(
            line_number=line_number,
            raw=raw_line,
            timestamp=timestamp,
            level=level,
            stream=stream,
            pod=pod,
            namespace=namespace or self.default_namespace,
            container=container,
            node=node,
            message=msg,
        )

    def _parse_kubelet_match(self, match: re.Match, line_number: int, raw_line: str) -> LogEntry:
        sev_char = match.group("severity")
        level_map = {"I": "INFO", "W": "WARN", "E": "ERROR", "F": "FATAL"}
        level = level_map.get(sev_char, "INFO")
        msg = match.group("message")
        pod, namespace, container, node = self._extract_k8s_identifiers(msg)

        return LogEntry(
            line_number=line_number,
            raw=raw_line,
            level=level,
            component="kubelet",
            pod=pod,
            namespace=namespace or self.default_namespace,
            container=container,
            node=node,
            message=msg,
            metadata={"pid": match.group("pid"), "source_file": match.group("file")},
        )

    def _parse_event_match(self, match: re.Match, line_number: int, raw_line: str) -> LogEntry:
        evt_type = match.group("type")
        reason = match.group("reason")
        from_comp = match.group("from")
        msg = match.group("message")

        level = "WARN" if evt_type == "Warning" else "INFO"
        if reason in ["OOMKilled", "FailedSync", "FailedScheduling", "CrashLoopBackOff"]:
            level = "ERROR"

        pod, namespace, container, node = self._extract_k8s_identifiers(msg)

        return LogEntry(
            line_number=line_number,
            raw=raw_line,
            level=level,
            component=from_comp,
            pod=pod,
            namespace=namespace or self.default_namespace,
            container=container,
            node=node,
            message=f"[{reason}] {msg}",
            metadata={"event_reason": reason, "event_type": evt_type, "age": match.group("age")},
        )

    def _parse_get_event_match(self, match: re.Match, line_number: int, raw_line: str) -> LogEntry:
        evt_type = match.group("type")
        reason = match.group("reason")
        obj = match.group("object")
        msg = match.group("message")

        level = "WARN" if evt_type == "Warning" else "INFO"
        if reason in ["OOMKilled", "FailedSync", "CrashLoopBackOff"]:
            level = "ERROR"

        pod = None
        if obj.startswith("pod/"):
            pod = obj.replace("pod/", "")
        elif "/" in obj:
            parts = obj.split("/")
            if len(parts) == 2 and parts[0] in ["pod", "deployment", "statefulset"]:
                pod = parts[1]

        msg_pod, msg_ns, container, node = self._extract_k8s_identifiers(msg)

        return LogEntry(
            line_number=line_number,
            raw=raw_line,
            level=level,
            pod=pod or msg_pod,
            namespace=msg_ns or self.default_namespace,
            container=container,
            node=node,
            message=f"[{reason}] {msg}",
            metadata={"event_reason": reason, "event_type": evt_type, "object": obj, "last_seen": match.group("last_seen")},
        )

    def _parse_generic_line(self, line: str, line_number: int) -> LogEntry:
        # Detect timestamp
        timestamp = None
        ts_match = ISO_TIMESTAMP_PATTERN.search(line)
        if ts_match:
            timestamp = self._parse_timestamp(ts_match.group("timestamp"))

        # Detect level
        level = self._detect_level(line)

        # Extract k8s entities
        pod, namespace, container, node = self._extract_k8s_identifiers(line)

        # Detect component e.g. [auth-service] or coredns[123]
        component = None
        comp_match = re.search(r"\[([a-zA-Z0-9_\-\.]{3,30})\]", line)
        if comp_match:
            cand = comp_match.group(1).lower()
            if cand not in ["error", "warn", "warning", "info", "debug", "fatal"]:
                component = comp_match.group(1)

        return LogEntry(
            line_number=line_number,
            raw=line,
            timestamp=timestamp,
            level=level,
            pod=pod,
            namespace=namespace or self.default_namespace,
            container=container,
            node=node,
            component=component,
            message=line,
        )

    def _detect_level(self, text: str) -> str:
        match = LOG_LEVEL_PATTERN.search(text)
        if match:
            return self._normalize_level(match.group("level"))
        if any(err in text.lower() for err in ["exception", "fatal error", "panic:", "oomkilled", "crashloopbackoff"]):
            return "ERROR"
        return "INFO"

    def _normalize_level(self, level_str: str) -> str:
        val = level_str.strip().upper()
        if val in ["ERR", "ERROR"]:
            return "ERROR"
        if val in ["WARN", "WARNING"]:
            return "WARN"
        if val in ["FATAL", "CRITICAL", "PANIC"]:
            return "FATAL"
        if val in ["DEBUG", "TRACE"]:
            return "DEBUG"
        return "INFO"

    def _is_valid_identifier(self, name: Optional[str]) -> bool:
        if not name or len(name) < 2:
            return False
        if name.lower() in STOP_WORDS:
            return False
        if name.lower().startswith(("pvc-", "pv-", "vol-", "volume-", "configmap-", "cm-", "kube-api-access-", "node.kubernetes.io")):
            return False
        if re.match(r"^\d+[a-zA-Z]{0,2}$", name):
            return False
        return True

    def _extract_k8s_identifiers(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        pod = None
        namespace = None
        container = None
        node = None

        ns_m = NAMESPACE_PATTERN.search(text)
        if ns_m:
            cand = ns_m.group(1)
            if self._is_valid_identifier(cand):
                namespace = cand

        ct_m = CONTAINER_PATTERN.search(text)
        if ct_m:
            cand = ct_m.group(1) or ct_m.group(2)
            if self._is_valid_identifier(cand):
                container = cand

        pod_m = POD_EXPLICIT_PATTERN.search(text)
        if pod_m:
            cand = pod_m.group(1)
            if self._is_valid_identifier(cand):
                pod = cand
        else:
            pod_m2 = POD_STRUCTURE_PATTERN.search(text)
            if pod_m2:
                cand = pod_m2.group(1) or pod_m2.group(2)
                if self._is_valid_identifier(cand):
                    pod = cand

        node_m = NODE_PATTERN.search(text)
        if node_m:
            cand = node_m.group(1) or node_m.group(2)
            if self._is_valid_identifier(cand):
                node = cand

        return pod, namespace, container, node

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        try:
            return date_parser.parse(ts_str)
        except Exception:
            return None
