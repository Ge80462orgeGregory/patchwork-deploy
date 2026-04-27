"""Tests for the diff engine and deployment planner."""

import pytest
from patchwork.core import ServiceConfig
from patchwork.diff import diff_configs, build_deployment_diff, ConfigChange
from patchwork.planner import plan_from_diff, DeployPlan


def make_config(name="web", image="nginx:1.0", replicas=2, env=None):
    return ServiceConfig(name=name, image=image, replicas=replicas, env=env or {})


class TestDiffConfigs:
    def test_identical_configs_no_changes(self):
        cfg = make_config()
        result = diff_configs(cfg, cfg)
        assert not result.has_changes
        assert result.changes == []

    def test_image_change_detected(self):
        old = make_config(image="nginx:1.0")
        new = make_config(image="nginx:2.0")
        result = diff_configs(old, new)
        assert result.has_changes
        image_change = next(c for c in result.changes if c.key == 'image')
        assert image_change.change_type == 'modified'
        assert image_change.old_value == "nginx:1.0"
        assert image_change.new_value == "nginx:2.0"

    def test_replica_change_detected(self):
        old = make_config(replicas=2)
        new = make_config(replicas=5)
        result = diff_configs(old, new)
        assert result.has_changes
        rep_change = next(c for c in result.changes if c.key == 'replicas')
        assert rep_change.change_type == 'modified'

    def test_env_added(self):
        old = make_config(env={"DEBUG": "false"})
        new = make_config(env={"DEBUG": "false", "NEW_VAR": "hello"})
        result = diff_configs(old, new)
        added = [c for c in result.changes if c.change_type == 'added']
        assert any(c.key == 'NEW_VAR' for c in added)

    def test_env_removed(self):
        old = make_config(env={"OLD_VAR": "bye", "KEEP": "yes"})
        new = make_config(env={"KEEP": "yes"})
        result = diff_configs(old, new)
        removed = [c for c in result.changes if c.change_type == 'removed']
        assert any(c.key == 'OLD_VAR' for c in removed)

    def test_summary_with_changes(self):
        old = make_config(image="nginx:1.0", replicas=1)
        new = make_config(image="nginx:2.0", replicas=3)
        result = diff_configs(old, new)
        summary = result.summary()
        assert "web" in summary
        assert "~" in summary


class TestBuildDeploymentDiff:
    def test_detects_new_service(self):
        old = {}
        new = {"web": make_config()}
        diff = build_deployment_diff(old, new)
        assert "web" in diff.to_add

    def test_detects_removed_service(self):
        old = {"web": make_config()}
        new = {}
        diff = build_deployment_diff(old, new)
        assert "web" in diff.to_remove

    def test_detects_updated_service(self):
        old = {"web": make_config(image="nginx:1.0")}
        new = {"web": make_config(image="nginx:2.0")}
        diff = build_deployment_diff(old, new)
        assert "web" in diff.to_update


class TestPlanFromDiff:
    def test_empty_plan_for_no_changes(self):
        cfg = make_config()
        diff = diff_configs(cfg, cfg)
        plan = plan_from_diff(diff, cfg)
        assert len(plan) == 0

    def test_image_update_generates_pull_and_update(self):
        old = make_config(image="nginx:1.0")
        new = make_config(image="nginx:2.0")
        diff = diff_configs(old, new)
        plan = plan_from_diff(diff, new)
        commands = [s.command for s in plan.steps]
        assert any("docker pull" in cmd for cmd in commands)
        assert any("docker service update" in cmd for cmd in commands)

    def test_scale_step_included(self):
        old = make_config(replicas=1)
        new = make_config(replicas=4)
        diff = diff_configs(old, new)
        plan = plan_from_diff(diff, new)
        assert any("scale" in s.command for s in plan.steps)

    def test_verify_step_is_non_critical(self):
        old = make_config(image="nginx:1.0")
        new = make_config(image="nginx:2.0")
        diff = diff_configs(old, new)
        plan = plan_from_diff(diff, new)
        verify = next(s for s in plan.steps if "Verify" in s.description)
        assert not verify.critical
