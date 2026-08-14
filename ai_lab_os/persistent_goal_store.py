from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_lab_os.task_planner import TaskPlanContract


@dataclass(frozen=True)
class PersistentTaskState:
    task_id: str
    status: str = "pending"
    attempts: int = 0
    message: str = ""
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "attempts": self.attempts,
            "message": self.message,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistentTaskState":
        return cls(
            task_id=str(payload["task_id"]),
            status=str(payload.get("status", "pending")),
            attempts=int(payload.get("attempts", 0)),
            message=str(payload.get("message", "")),
            evidence=tuple(str(item) for item in payload.get("evidence", [])),
        )


@dataclass(frozen=True)
class PersistentGoalState:
    goal_id: str
    status: str
    plan: dict[str, Any]
    tasks: tuple[PersistentTaskState, ...]
    resume_cursor: str | None = None
    cycles: int = 0
    events: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "0.6.1"

    @classmethod
    def from_plan(cls, plan: TaskPlanContract) -> "PersistentGoalState":
        return cls(
            goal_id=plan.goal_id,
            status="pending",
            plan=plan.to_dict(),
            tasks=tuple(PersistentTaskState(task.task_id) for task in plan.tasks),
            resume_cursor=plan.tasks[0].task_id if plan.tasks else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "goal_id": self.goal_id,
            "status": self.status,
            "plan": self.plan,
            "tasks": [task.to_dict() for task in self.tasks],
            "resume_cursor": self.resume_cursor,
            "cycles": self.cycles,
            "events": list(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistentGoalState":
        return cls(
            schema_version=str(payload.get("schema_version", "0.6.1")),
            goal_id=str(payload["goal_id"]),
            status=str(payload.get("status", "pending")),
            plan=dict(payload.get("plan", {})),
            tasks=tuple(PersistentTaskState.from_dict(item) for item in payload.get("tasks", [])),
            resume_cursor=payload.get("resume_cursor"),
            cycles=int(payload.get("cycles", 0)),
            events=tuple(str(item) for item in payload.get("events", [])),
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=str(payload.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )


class JsonGoalStore:
    """Small dependency-free persistent goal store for V0.6.

    One JSON file contains goal records keyed by goal_id. Writes are atomic via a
    temporary file + replace so process interruption cannot leave a half-written
    state file under normal filesystem semantics.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read_all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("persistent goal store root must be an object")
        return {str(key): dict(value) for key, value in payload.items()}

    def _write_all(self, payload: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, state: PersistentGoalState) -> None:
        payload = self._read_all()
        data = state.to_dict()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload[state.goal_id] = data
        self._write_all(payload)

    def load(self, goal_id: str) -> PersistentGoalState:
        key = goal_id.strip()
        if not key:
            raise ValueError("goal_id cannot be empty")
        payload = self._read_all()
        try:
            return PersistentGoalState.from_dict(payload[key])
        except KeyError as exc:
            raise LookupError(f"persistent goal not found: {key}") from exc

    def delete(self, goal_id: str) -> None:
        key = goal_id.strip()
        payload = self._read_all()
        if key not in payload:
            raise LookupError(f"persistent goal not found: {key}")
        del payload[key]
        self._write_all(payload)

    def list(self) -> tuple[PersistentGoalState, ...]:
        payload = self._read_all()
        return tuple(
            PersistentGoalState.from_dict(payload[key])
            for key in sorted(payload)
        )
