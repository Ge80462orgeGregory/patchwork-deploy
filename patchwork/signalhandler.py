"""Graceful shutdown signal handler for pipeline runs."""
from __future__ import annotations

import signal
import threading
from dataclasses import dataclass, field
from typing import Callable, List


class SignalError(Exception):
    """Raised when signal handling cannot be configured."""

    def __repr__(self) -> str:
        return f"SignalError({self.args[0]!r})"


@dataclass
class ShutdownEvent:
    """Tracks whether a graceful shutdown has been requested."""

    _event: threading.Event = field(default_factory=threading.Event, init=False)
    signal_received: int | None = field(default=None, init=False)

    def request(self, signum: int) -> None:
        self.signal_received = signum
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def clear(self) -> None:
        self.signal_received = None
        self._event.clear()

    def __repr__(self) -> str:
        return f"ShutdownEvent(is_set={self.is_set()}, signal={self.signal_received})"


@dataclass
class SignalHandler:
    """Registers OS signal listeners and notifies registered callbacks."""

    shutdown: ShutdownEvent = field(default_factory=ShutdownEvent)
    _callbacks: List[Callable[[int], None]] = field(default_factory=list, init=False)
    _original: dict = field(default_factory=dict, init=False)

    def register(self, signals: List[int] | None = None) -> None:
        sigs = signals or [signal.SIGINT, signal.SIGTERM]
        for sig in sigs:
            try:
                self._original[sig] = signal.signal(sig, self._handle)
            except (OSError, ValueError) as exc:
                raise SignalError(f"Cannot register signal {sig}: {exc}") from exc

    def unregister(self) -> None:
        for sig, original in self._original.items():
            try:
                signal.signal(sig, original)
            except (OSError, ValueError):
                pass
        self._original.clear()

    def add_callback(self, cb: Callable[[int], None]) -> None:
        self._callbacks.append(cb)

    def _handle(self, signum: int, _frame) -> None:
        self.shutdown.request(signum)
        for cb in self._callbacks:
            try:
                cb(signum)
            except Exception:  # noqa: BLE001
                pass

    def __repr__(self) -> str:
        return f"SignalHandler(shutdown={self.shutdown}, callbacks={len(self._callbacks)})"
