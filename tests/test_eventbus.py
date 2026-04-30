"""Tests for patchwork.eventbus."""
from __future__ import annotations

import pytest
from patchwork.eventbus import Event, EventBus


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class TestEvent:
    def test_to_dict_contains_required_keys(self):
        e = Event(topic="deploy.start", payload={"service": "api"})
        d = e.to_dict()
        assert d["topic"] == "deploy.start"
        assert d["payload"] == {"service": "api"}
        assert "timestamp" in d

    def test_repr_contains_topic(self):
        e = Event(topic="deploy.done", payload={})
        assert "deploy.done" in repr(e)


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestEventBusSubscribe:
    def test_handler_called_on_publish(self):
        bus = EventBus()
        received: list = []
        bus.subscribe("test.topic", lambda e: received.append(e))
        bus.publish("test.topic", {"x": 1})
        assert len(received) == 1
        assert received[0].payload == {"x": 1}

    def test_handler_not_called_for_other_topic(self):
        bus = EventBus()
        received: list = []
        bus.subscribe("a", lambda e: received.append(e))
        bus.publish("b", {})
        assert received == []

    def test_multiple_handlers_same_topic(self):
        bus = EventBus()
        calls: list = []
        bus.subscribe("t", lambda e: calls.append(1))
        bus.subscribe("t", lambda e: calls.append(2))
        bus.publish("t", {})
        assert calls == [1, 2]

    def test_unsubscribe_removes_handler(self):
        bus = EventBus()
        calls: list = []
        handler = lambda e: calls.append(e)  # noqa: E731
        bus.subscribe("t", handler)
        bus.unsubscribe("t", handler)
        bus.publish("t", {})
        assert calls == []

    def test_unsubscribe_unknown_handler_is_safe(self):
        bus = EventBus()
        bus.unsubscribe("nonexistent", lambda e: None)  # should not raise


class TestEventBusHistory:
    def test_publish_records_event(self):
        bus = EventBus()
        bus.publish("a", {"k": "v"})
        assert len(bus) == 1

    def test_history_filtered_by_topic(self):
        bus = EventBus()
        bus.publish("a", {})
        bus.publish("b", {})
        bus.publish("a", {})
        assert len(bus.history("a")) == 2
        assert len(bus.history("b")) == 1

    def test_history_all_when_no_topic(self):
        bus = EventBus()
        bus.publish("a", {})
        bus.publish("b", {})
        assert len(bus.history()) == 2

    def test_clear_history(self):
        bus = EventBus()
        bus.publish("a", {})
        bus.clear_history()
        assert len(bus) == 0
        assert bus.history() == []

    def test_publish_returns_event(self):
        bus = EventBus()
        event = bus.publish("deploy.start", {"service": "web"})
        assert isinstance(event, Event)
        assert event.topic == "deploy.start"
