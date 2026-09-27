"""
Aegis Structured Event System & Telemetry Bus
Provides typed lifecycle events, correlation IDs, and event dispatching for observability.
"""

from __future__ import annotations
import uuid
import time
from typing import Dict, Any, List, Callable, Optional
from pydantic import BaseModel, Field


def generate_id(prefix: str = "evt") -> str:
    """Generates a unique, timestamp-prefixed identifier."""
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


class Event(BaseModel):
    """Base model for all Aegis structured events."""
    event_id: str = Field(default_factory=lambda: generate_id("evt"))
    correlation_id: str = Field(default_factory=lambda: generate_id("corr"))
    timestamp: float = Field(default_factory=time.time)
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DiscoveryStartedEvent(Event):
    event_type: str = "discovery.started"


class DiscoveryCompletedEvent(Event):
    event_type: str = "discovery.completed"


class ExecutionStartedEvent(Event):
    event_type: str = "execution.started"


class ExecutionCompletedEvent(Event):
    event_type: str = "execution.completed"


class EvidenceRecordedEvent(Event):
    event_type: str = "evidence.recorded"


class FailureFingerprintedEvent(Event):
    event_type: str = "failure.fingerprinted"


class ReleaseVerdictComputedEvent(Event):
    event_type: str = "release.verdict_computed"


class EventBus:
    """In-memory publish-subscribe event dispatcher."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[[Event], None]]] = {}
        self._history: List[Event] = []

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Subscribes a callback handler to a specific event type or '*' for all events."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event: Event) -> None:
        """Publishes an event synchronously to all registered listeners."""
        self._history.append(event)
        
        # Exact match listeners
        for listener in self._listeners.get(event.event_type, []):
            try:
                listener(event)
            except Exception:
                pass

        # Wildcard listeners
        for listener in self._listeners.get("*", []):
            try:
                listener(event)
            except Exception:
                pass

    def get_history(self) -> List[Event]:
        """Returns the full chronological event log."""
        return list(self._history)

    def clear(self) -> None:
        """Clears listeners and event history."""
        self._listeners.clear()
        self._history.clear()


# Global default event bus instance
default_event_bus = EventBus()
