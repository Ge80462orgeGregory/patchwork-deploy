"""Tests for patchwork.notifier."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from patchwork.executor import ExecutionReport, StepResult
from patchwork.notifier import NotificationResult, Notifier
from patchwork.planner import DeployStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(success: bool = True, n_steps: int = 2) -> ExecutionReport:
    steps = [
        StepResult(
            step=DeployStep(service="svc", action="update", command=f"cmd{i}"),
            success=success,
            output=f"out{i}",
            error="" if success else "boom",
        )
        for i in range(n_steps)
    ]
    return ExecutionReport(steps=steps, duration_seconds=1.23)


# ---------------------------------------------------------------------------
# NotificationResult
# ---------------------------------------------------------------------------

class TestNotificationResult:
    def test_success_flag(self):
        r = NotificationResult(channel="stdout", success=True, message="ok")
        assert r.success is True

    def test_failure_flag(self):
        r = NotificationResult(channel="webhook", success=False, message="err")
        assert r.success is False


# ---------------------------------------------------------------------------
# Notifier — stdout channel
# ---------------------------------------------------------------------------

class TestNotifierStdout:
    def test_stdout_always_succeeds(self, capsys):
        notifier = Notifier()
        report = _make_report(success=True)
        results = notifier.notify(report)
        assert any(r.channel == "stdout" and r.success for r in results)

    def test_stdout_prints_success(self, capsys):
        notifier = Notifier()
        notifier.notify(_make_report(success=True))
        out = capsys.readouterr().out
        assert "SUCCESS" in out

    def test_stdout_prints_failure(self, capsys):
        notifier = Notifier()
        notifier.notify(_make_report(success=False))
        out = capsys.readouterr().out
        assert "FAILURE" in out

    def test_no_webhook_only_one_result(self, capsys):
        notifier = Notifier(webhook_url=None)
        results = notifier.notify(_make_report())
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Notifier — webhook channel
# ---------------------------------------------------------------------------

class TestNotifierWebhook:
    def test_webhook_called_with_json(self, capsys):
        captured: list[bytes] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                captured.append(self.rfile.read(length))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):  # silence server logs
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        t = Thread(target=server.handle_request, daemon=True)
        t.start()

        notifier = Notifier(webhook_url=f"http://127.0.0.1:{port}")
        results = notifier.notify(_make_report())
        t.join(timeout=3)
        server.server_close()

        webhook_results = [r for r in results if r.channel == "webhook"]
        assert webhook_results[0].success is True
        payload = json.loads(captured[0])
        assert "success" in payload

    def test_webhook_failure_returns_failed_result(self, capsys):
        notifier = Notifier(webhook_url="http://127.0.0.1:1", timeout=1)
        results = notifier.notify(_make_report())
        webhook_results = [r for r in results if r.channel == "webhook"]
        assert webhook_results[0].success is False
