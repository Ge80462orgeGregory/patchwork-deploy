"""Tests for patchwork.changewindow."""
from datetime import datetime, time
from pathlib import Path

import pytest

from patchwork.changewindow import ChangeWindow, ChangeWindowError, ChangeWindowStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _win(
    name: str = "business-hours",
    days: list = None,
    start: str = "09:00",
    end: str = "17:00",
    enabled: bool = True,
) -> ChangeWindow:
    return ChangeWindow(
        name=name,
        days=days if days is not None else [0, 1, 2, 3, 4],
        start=time.fromisoformat(start),
        end=time.fromisoformat(end),
        enabled=enabled,
    )


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "windows.json"


@pytest.fixture
def store(store_path: Path) -> ChangeWindowStore:
    return ChangeWindowStore(store_path)


# ---------------------------------------------------------------------------
# ChangeWindow unit tests
# ---------------------------------------------------------------------------

class TestChangeWindow:
    def test_allows_inside_window(self):
        w = _win(days=[0], start="08:00", end="18:00")
        # Monday 10:00
        dt = datetime(2024, 1, 1, 10, 0)  # 2024-01-01 is a Monday
        assert w.allows(dt) is True

    def test_rejects_outside_hours(self):
        w = _win(days=[0], start="09:00", end="17:00")
        dt = datetime(2024, 1, 1, 18, 0)
        assert w.allows(dt) is False

    def test_rejects_wrong_day(self):
        w = _win(days=[0])  # Monday only
        dt = datetime(2024, 1, 2, 10, 0)  # Tuesday
        assert w.allows(dt) is False

    def test_disabled_window_always_allows(self):
        w = _win(days=[], enabled=False)
        assert w.allows(datetime(2024, 1, 1, 3, 0)) is True

    def test_round_trip(self):
        w = _win()
        w2 = ChangeWindow.from_dict(w.to_dict())
        assert w2.name == w.name
        assert w2.days == w.days
        assert w2.start == w.start
        assert w2.end == w.end
        assert w2.enabled == w.enabled

    def test_repr_contains_name(self):
        w = _win(name="release-window")
        assert "release-window" in repr(w)


# ---------------------------------------------------------------------------
# ChangeWindowStore tests
# ---------------------------------------------------------------------------

class TestChangeWindowStore:
    def test_empty_store_allows_deployment(self, store):
        assert store.is_deployment_allowed() is True

    def test_add_and_retrieve(self, store):
        store.add(_win())
        assert len(store.all()) == 1

    def test_duplicate_name_raises(self, store):
        store.add(_win())
        with pytest.raises(ChangeWindowError):
            store.add(_win())

    def test_remove_existing(self, store):
        store.add(_win())
        store.remove("business-hours")
        assert store.all() == []

    def test_remove_missing_raises(self, store):
        with pytest.raises(ChangeWindowError):
            store.remove("ghost")

    def test_persists_across_instances(self, store_path):
        s1 = ChangeWindowStore(store_path)
        s1.add(_win())
        s2 = ChangeWindowStore(store_path)
        assert len(s2.all()) == 1

    def test_deployment_blocked_outside_all_windows(self, store):
        # Saturday window only
        store.add(_win(days=[5], start="10:00", end="12:00"))
        monday_morning = datetime(2024, 1, 1, 9, 0)
        assert store.is_deployment_allowed(monday_morning) is False

    def test_deployment_allowed_inside_any_window(self, store):
        store.add(_win(name="w1", days=[0], start="08:00", end="10:00"))
        store.add(_win(name="w2", days=[0], start="14:00", end="16:00"))
        assert store.is_deployment_allowed(datetime(2024, 1, 1, 9, 0)) is True
        assert store.is_deployment_allowed(datetime(2024, 1, 1, 15, 0)) is True
