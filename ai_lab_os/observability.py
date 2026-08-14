from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    event_type: str
    message: str
    step_id: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class InMemoryEventLog:
    def __init__(self) -> None:
        self._events: list[TaskEvent] = []

    def append(self, event: TaskEvent) -> None:
        self._events.append(event)

    def for_task(self, task_id: str) -> tuple[TaskEvent, ...]:
        return tuple(event for event in self._events if event.task_id == task_id)
