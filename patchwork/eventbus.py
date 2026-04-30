"""Simple in-process event bus for publishing and subscribing to deployment events."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any
from datetime import datetime, timezone


@dataclass
class Event:
    """Represents a single published event."""
    topic: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return f"Event(topic={self.topic!r}, timestamp={self.timestamp.isoformat()!r})"


Handler = Callable[[Event], None]


class EventBus:
    """Lightweight publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Handler]] = {}
        self._history: List[Event] = []

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Register *handler* to be called when *topic* is published."""
        self._subscribers.setdefault(topic, []).append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        """Remove a previously registered handler."""
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, topic: str, payload: Dict[str, Any]) -> Event:
        """Create an Event and dispatch it to all subscribers of *topic*."""
        event = Event(topic=topic, payload=payload)
        self._history.append(event)
        for handler in list(self._subscribers.get(topic, [])):
            handler(event)
        return event

    def history(self, topic: str | None = None) -> List[Event]:
        """Return recorded events, optionally filtered by topic."""
        if topic is None:
            return list(self._history)
        return [e for e in self._history if e.topic == topic]

    def clear_history(self) -> None:
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)
