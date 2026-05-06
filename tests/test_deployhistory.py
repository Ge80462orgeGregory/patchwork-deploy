"""Tests for patchwork.deployhistory."""
import json
import time
import pytest
from pathlib import Path

from patchwork.deployhistory import DeployRecord, DeployHistory, HistoryError


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "history.json"


@pytest.fixture
def history(store_path: Path) -> DeployHistory:
    return DeployHistory(store_path)


def _rec(service="api", env="prod", image="api:1.0", status="success", notes="") -> DeployRecord:
    return DeployRecord(service=service, environment=env, image=image, status=status, notes=notes)


class TestDeployRecord:
    def test_round_trip(self):
        r = _rec(notes="initial deploy")
        restored = DeployRecord.from_dict(r.to_dict())
        assert restored.service == r.service
        assert restored.environment == r.environment
        assert restored.image == r.image
        assert restored.status == r.status
        assert restored.notes == r.notes
        assert restored.timestamp == pytest.approx(r.timestamp)

    def test_repr_contains_key_fields(self):
        r = _rec()
        text = repr(r)
        assert "api" in text
        assert "prod" in text
        assert "success" in text

    def test_missing_notes_defaults_to_empty(self):
        data = _rec().to_dict()
        del data["notes"]
        r = DeployRecord.from_dict(data)
        assert r.notes == ""


class TestDeployHistory:
    def test_empty_initially(self, history: DeployHistory):
        assert len(history) == 0
        assert history.all() == []

    def test_record_persists(self, store_path: Path):
        h = DeployHistory(store_path)
        h.record(_rec())
        h2 = DeployHistory(store_path)
        assert len(h2) == 1
        assert h2.all()[0].service == "api"

    def test_for_service_filters_correctly(self, history: DeployHistory):
        history.record(_rec(service="api"))
        history.record(_rec(service="worker"))
        history.record(_rec(service="api"))
        assert len(history.for_service("api")) == 2
        assert len(history.for_service("worker")) == 1

    def test_latest_returns_most_recent(self, history: DeployHistory):
        history.record(_rec(service="api", image="api:1.0"))
        history.record(_rec(service="api", image="api:2.0"))
        assert history.latest("api").image == "api:2.0"

    def test_latest_returns_none_for_unknown_service(self, history: DeployHistory):
        assert history.latest("ghost") is None

    def test_last_successful_skips_failures(self, history: DeployHistory):
        history.record(_rec(service="api", image="api:1.0", status="success"))
        history.record(_rec(service="api", image="api:2.0", status="failure"))
        result = history.last_successful("api")
        assert result is not None
        assert result.image == "api:1.0"

    def test_last_successful_none_when_all_failed(self, history: DeployHistory):
        history.record(_rec(status="failure"))
        assert history.last_successful("api") is None

    def test_len_reflects_total_records(self, history: DeployHistory):
        for _ in range(5):
            history.record(_rec())
        assert len(history) == 5
