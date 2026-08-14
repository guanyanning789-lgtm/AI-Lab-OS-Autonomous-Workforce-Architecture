from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState


@dataclass(frozen=True)
class GoalTaskSnapshot:
    task_id: str
    status: str
    attempts: int
    message: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class GoalStatusSnapshot:
    goal_id: str
    status: str
    resume_cursor: str | None
    cycles: int
    completed_tasks: int
    total_tasks: int
    progress_percent: int
    last_error: str | None
    created_at: str
    updated_at: str
    tasks: tuple[GoalTaskSnapshot, ...]
    events: tuple[str, ...]


class GoalQueryService:
    """Read-only product query boundary over the durable goal store."""

    def __init__(self, goal_store: JsonGoalStore) -> None:
        self._goal_store = goal_store

    def get_goal(self, goal_id: str) -> GoalStatusSnapshot:
        return self._snapshot(self._goal_store.load(goal_id))

    def list_goals(self, *, status: str | None = None) -> tuple[GoalStatusSnapshot, ...]:
        states = self._goal_store.list()
        if status is not None:
            wanted = status.strip()
            if not wanted:
                raise ValueError("status filter cannot be blank")
            states = tuple(state for state in states if state.status == wanted)
        return tuple(self._snapshot(state) for state in states)

    def get_events(self, goal_id: str, *, after: int = 0) -> tuple[str, ...]:
        if after < 0:
            raise ValueError("after must be >= 0")
        state = self._goal_store.load(goal_id)
        return state.events[after:]

    @staticmethod
    def _last_error(state: PersistentGoalState) -> str | None:
        for task in reversed(state.tasks):
            if task.message.strip():
                return task.message.strip()
        for event in reversed(state.events):
            if event.startswith("FAILED:"):
                parts = event.split(":", 2)
                return parts[2].strip() if len(parts) == 3 and parts[2].strip() else event
        return None

    @classmethod
    def _snapshot(cls, state: PersistentGoalState) -> GoalStatusSnapshot:
        tasks = tuple(
            GoalTaskSnapshot(
                task_id=task.task_id,
                status=task.status,
                attempts=task.attempts,
                message=task.message,
                evidence=task.evidence,
            )
            for task in state.tasks
        )
        completed = sum(1 for task in state.tasks if task.status == "complete")
        total = len(state.tasks)
        progress = 100 if total == 0 and state.status == "complete" else (0 if total == 0 else int(completed * 100 / total))
        return GoalStatusSnapshot(
            goal_id=state.goal_id,
            status=state.status,
            resume_cursor=state.resume_cursor,
            cycles=state.cycles,
            completed_tasks=completed,
            total_tasks=total,
            progress_percent=progress,
            last_error=cls._last_error(state),
            created_at=state.created_at,
            updated_at=state.updated_at,
            tasks=tasks,
            events=state.events,
        )
