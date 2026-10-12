"""
Tests for Multi-format Kubernetes Log Parser.
"""

import pytest
from k8s_investigate.parser import LogParser


def test_parse_cri_format():
    parser = LogParser()
    raw = "2026-10-10T00:15:30.123456789Z stdout F [INFO] Server started on port 8080"
    entries = parser.parse_text(raw)
    
    assert len(entries) == 1
    entry = entries[0]
    assert entry.line_number == 1
    assert entry.stream == "stdout"
    assert entry.level == "INFO"
    assert "Server started on port 8080" in entry.message
    assert entry.timestamp is not None
    assert entry.timestamp.year == 2026


def test_parse_json_format():
    parser = LogParser()
    raw = '{"time": "2026-10-10T00:15:30Z", "level": "error", "message": "Failed to connect to redis", "pod": "web-pod-123"}'
    entries = parser.parse_text(raw)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.level == "ERROR"
    assert entry.message == "Failed to connect to redis"
    assert entry.pod == "web-pod-123"
    assert entry.timestamp is not None


def test_parse_k8s_event_table():
    parser = LogParser()
    raw = """
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Warning  OOMKilled  3m (x1 over 3m)    kubelet            Pod memory limit exceeded: 512Mi
  Normal   Scheduled  10m                default-scheduler  Successfully assigned default/web-pod to node-1
"""
    entries = parser.parse_text(raw)
    assert len(entries) >= 2
    oom_entry = [e for e in entries if "OOMKilled" in e.message][0]
    assert oom_entry.level == "ERROR"
    assert oom_entry.component == "kubelet"
    assert oom_entry.metadata.get("event_reason") == "OOMKilled"


def test_parse_multiline_stack_trace():
    parser = LogParser()
    raw = """2026-10-10T00:15:30.000Z stderr F Traceback (most recent call last):
  File "server.py", line 42, in handle_request
    raise ValueError("Invalid configuration detected")
ValueError: Invalid configuration detected
2026-10-10T00:15:31.000Z stdout F [INFO] Restarting worker"""

    entries = parser.parse_text(raw)
    assert len(entries) == 2
    tb_entry = entries[0]
    assert tb_entry.is_stack_trace is True
    assert "handle_request" in tb_entry.message
    assert "ValueError: Invalid configuration detected" in tb_entry.message
