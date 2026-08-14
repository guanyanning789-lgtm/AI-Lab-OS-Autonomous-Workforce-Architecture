from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_lab_os.persistent_goal_store import PersistentGoalState


@dataclass(frozen=True)
class ExecutionHistoryRecord:
    goal_id: str
    skill_id: str | None
    status: str
    cycles: int
    completed_tasks: tuple[str, ...]
    failed_tasks: tuple[str, ...]
    total_attempts: int
    evidence: tuple[str, ...]
    events: tuple[str, ...]
    recorded_at: str
    schema_version: str = "0.6.4"

    @classmethod
    def from_goal_state(cls, state: PersistentGoalState) -> "ExecutionHistoryRecord":
        skill_ids = {
            str(task.get("metadata", {}).get("skill_id", "")).strip()
            for task in state.plan.get("tasks", [])
            if isinstance(task, dict)
        }
        skill_ids.discard("")
        skill_id = next(iter(skill_ids)) if len(skill_ids) == 1 else None
        completed = tuple(task.task_id for task in state.tasks if task.status == "complete")
        failed = tuple(
            task.task_id
            for task in state.tasks
            if task.status in {"failed", "replan"}
        )
        evidence = tuple(
            item
            for task in state.tasks
            for item in task.evidence
            if item
        )
        return cls(
            goal_id=state.goal_id,
            skill_id=skill_id,
            status=state.status,
            cycles=state.cycles,
            completed_tasks=completed,
            failed_tasks=failed,
            total_attempts=sum(task.attempts for task in state.tasks),
            evidence=evidence,
            events=state.events,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "goal_id": self.goal_id,
            "skill_id": self.skill_id,
            "status": self.status,
            "cycles": self.cycles,
            "completed_tasks": list(self.completed_tasks),
            "failed_tasks": list(self.failed_tasks),
            "total_attempts": self.total_attempts,
            "evidence": list(self.evidence),
            "events": list(self.events),
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionHistoryRecord":
        skill_id = payload.get("skill_id")
        return cls(
            schema_version=str(payload.get("schema_version", "0.6.4")),
            goal_id=str(payload["goal_id"]),
            skill_id=None if skill_id is None else str(skill_id),
            status=str(payload.get("status", "unknown")),
            cycles=int(payload.get("cycles", 0)),
            completed_tasks=tuple(str(item) for item in payload.get("completed_tasks", [])),
            failed_tasks=tuple(str(item) for item in payload.get("failed_tasks", [])),
            total_attempts=int(payload.get("total_attempts", 0)),
            evidence=tuple(str(item) for item in payload.get("evidence", [])),
            events=tuple(str(item) for item in payload.get("events", [])),
            recorded_at=str(payload.get("recorded_at", "")),
        )


class JsonExecutionHistory:
    """Append-only execution memory with simple indexed filtering."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: ExecutionHistoryRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def append_goal_state(self, state: PersistentGoalState) -> ExecutionHistoryRecord:
        record = ExecutionHistoryRecord.from_goal_state(state)
        self.append(record)
        return record

    def list(
        self,
        *,
        goal_id: str | None = None,
        skill_id: str | None = None,
        status: str | None = None,
    ) -> tuple[ExecutionHistoryRecord, ...]:
        if not self.path.exists():
            return ()
        records: list[ExecutionHistoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = ExecutionHistoryRecord.from_dict(json.loads(line))
            if goal_id is not None and record.goal_id != goal_id:
                continue
            if skill_id is not None and record.skill_id != skill_id:
                continue
            if status is not None and record.status != status:
                continue
            records.append(record)
        return tuple(records)

    def latest(self, *, goal_id: str | None = None, skill_id: str | None = None) -> ExecutionHistoryRecord:
        records = self.list(goal_id=goal_id, skill_id=skill_id)
        if not records:
            raise LookupError("execution history record not found")
        return records[-1]
