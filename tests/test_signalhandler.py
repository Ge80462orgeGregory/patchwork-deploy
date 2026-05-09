"""Tests for patchwork.signalhandler."""
from __future__ import annotations

import signal
import threading

import pytest

from patchwork.signalhandler import ShutdownEvent, SignalError, SignalHandler


# ---------------------------------------------------------------------------
# ShutdownEvent
# ---------------------------------------------------------------------------

class TestShutdownEvent:
    def test_not_set_initially(self):
        ev = ShutdownEvent()
        assert not ev.is_set()

    def test_request_sets_event(self):
        ev = ShutdownEvent()
        ev.request(signal.SIGINT)
        assert ev.is_set()
        assert ev.signal_received == signal.SIGINT

    def test_clear_resets_state(self):
        ev = ShutdownEvent()
        ev.request(signal.SIGTERM)
        ev.clear()
        assert not ev.is_set()
        assert ev.signal_received is None

    def test_repr_contains_key_fields(self):
        ev = ShutdownEvent()
        r = repr(ev)
        assert "ShutdownEvent" in r
        assert "is_set" in r


# ---------------------------------------------------------------------------
# SignalHandler
# ---------------------------------------------------------------------------

class TestSignalHandler:
    def test_repr_contains_key_fields(self):
        h = SignalHandler()
        r = repr(h)
        assert "SignalHandler" in r
        assert "callbacks" in r

    def test_register_and_unregister_restores_original(self):
        original = signal.getsignal(signal.SIGUSR1)
        h = SignalHandler()
        h.register([signal.SIGUSR1])
        assert signal.getsignal(signal.SIGUSR1) is not original
        h.unregister()
        assert signal.getsignal(signal.SIGUSR1) == original

    def test_handle_sets_shutdown_event(self):
        h = SignalHandler()
        h.register([signal.SIGUSR1])
        try:
            signal.raise_signal(signal.SIGUSR1)
        finally:
            h.unregister()
        assert h.shutdown.is_set()
        assert h.shutdown.signal_received == signal.SIGUSR1

    def test_callback_invoked_on_signal(self):
        received: list[int] = []
        h = SignalHandler()
        h.add_callback(received.append)
        h.register([signal.SIGUSR2])
        try:
            signal.raise_signal(signal.SIGUSR2)
        finally:
            h.unregister()
        assert received == [signal.SIGUSR2]

    def test_callback_exception_does_not_propagate(self):
        def bad_cb(sig: int) -> None:
            raise RuntimeError("boom")

        h = SignalHandler()
        h.add_callback(bad_cb)
        h.register([signal.SIGUSR1])
        try:
            signal.raise_signal(signal.SIGUSR1)  # should not raise
        finally:
            h.unregister()
        assert h.shutdown.is_set()

    def test_multiple_callbacks_all_called(self):
        log: list[str] = []
        h = SignalHandler()
        h.add_callback(lambda s: log.append("a"))
        h.add_callback(lambda s: log.append("b"))
        h.register([signal.SIGUSR2])
        try:
            signal.raise_signal(signal.SIGUSR2)
        finally:
            h.unregister()
        assert log == ["a", "b"]
