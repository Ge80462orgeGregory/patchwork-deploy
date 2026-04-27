"""Tests for PlanExecutor."""

from unittest.mock import MagicMock, patch

import pytest

from patchwork.executor import ExecutionReport, PlanExecutor, StepResult
from patchwork.planner import DeployPlan, DeployStep
from patchwork.ssh import CommandResult, SSHError


def make_plan(*steps: tuple) -> DeployPlan:
    plan = DeployPlan(service="web")
    for desc, cmd, critical in steps:
        plan.add_step(desc, cmd, critical)
    return plan


def mock_client(host: str = "10.0.0.1") -> MagicMock:
    client = MagicMock()
    client.host = host
    return client


def cmd_ok(stdout: str = "") -> CommandResult:
    return CommandResult(exit_code=0, stdout=stdout, stderr="")


def cmd_fail(stderr: str = "error") -> CommandResult:
    return CommandResult(exit_code=1, stdout="", stderr=stderr)


class TestDryRun:
    def test_dry_run_no_ssh_calls(self):
        client = mock_client()
        plan = make_plan(("Pull image", "docker pull nginx", True))
        executor = PlanExecutor(client, dry_run=True)
        report = executor.execute(plan)
        client.run.assert_not_called()
        assert report.success

    def test_dry_run_all_steps_succeed(self):
        client = mock_client()
        plan = make_plan(
            ("step1", "cmd1", True),
            ("step2", "cmd2", False),
        )
        executor = PlanExecutor(client, dry_run=True)
        report = executor.execute(plan)
        assert len(report.results) == 2
        assert all(r.success for r in report.results)


class TestLiveExecution:
    def test_all_steps_succeed(self):
        client = mock_client()
        client.run.return_value = cmd_ok("done")
        plan = make_plan(
            ("Pull", "docker pull nginx", True),
            ("Scale", "docker service scale web=3", False),
        )
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        assert report.success
        assert len(report.results) == 2
        assert client.run.call_count == 2

    def test_critical_failure_aborts_plan(self):
        client = mock_client()
        client.run.side_effect = [cmd_fail("pull failed"), cmd_ok()]
        plan = make_plan(
            ("Pull", "docker pull bad:image", True),
            ("Restart", "docker service update web", True),
        )
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        assert not report.success
        assert len(report.results) == 1  # aborted after first critical failure
        assert client.run.call_count == 1

    def test_non_critical_failure_continues(self):
        client = mock_client()
        client.run.side_effect = [cmd_ok(), cmd_fail("scale failed"), cmd_ok()]
        plan = make_plan(
            ("Pull", "docker pull nginx", True),
            ("Scale", "docker service scale web=5", False),
            ("Notify", "echo done", False),
        )
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        assert not report.success
        assert len(report.results) == 3
        assert len(report.failed_steps) == 1

    def test_ssh_error_captured_as_failure(self):
        client = mock_client()
        client.run.side_effect = SSHError("connection lost")
        plan = make_plan(("Deploy", "docker service update web", True))
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        assert not report.success
        assert "connection lost" in report.results[0].error

    def test_empty_plan_returns_empty_report(self):
        client = mock_client()
        plan = DeployPlan(service="idle")
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        assert report.success
        assert len(report.results) == 0
        client.run.assert_not_called()

    def test_summary_format(self):
        client = mock_client(host="192.168.1.5")
        client.run.return_value = cmd_ok()
        plan = make_plan(("step", "cmd", True))
        executor = PlanExecutor(client)
        report = executor.execute(plan)
        summary = report.summary()
        assert "192.168.1.5" in summary
        assert "1/1" in summary
        assert "OK" in summary
