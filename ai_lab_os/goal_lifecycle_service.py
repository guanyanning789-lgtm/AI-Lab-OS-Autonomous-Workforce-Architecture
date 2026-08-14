from __future__ import annotations

from dataclasses import dataclass, replace

from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState


@dataclass(frozen=True)
class GoalLifecycleResult:
    goal_id: str
    previous_status: str
    status: str
    resume_cursor: str | None
    event: str


class GoalLifecycleService:
    """Explicit product lifecycle controls for durable goals.

    Pause/cancel only mutate durable control state. They do not attempt to kill an
    executor mid-instruction; callers should invoke controls at task boundaries.
    Resume re-enables a paused goal for the normal bounded Recovery runtime.
    """

    def __init__(self, goal_store: JsonGoalStore) -> None:
        self._goal_store = goal_store

    def pause(self, goal_id: str) -> GoalLifecycleResult:
        state = self._goal_store.load(goal_id)
        if state.status == "complete":
            raise ValueError("completed goal cannot be paused")
        if state.status == "cancelled":
            raise ValueError("cancelled goal cannot be paused")
        if state.status == "paused":
            return GoalLifecycleResult(state.goal_id, "paused", "paused", state.resume_cursor, "PAUSE:already_paused")
        return self._transition(state, "paused", "PAUSE")

    def cancel(self, goal_id: str) -> GoalLifecycleResult:
        state = self._goal_store.load(goal_id)
        if state.status == "complete":
            raise ValueError("completed goal cannot be cancelled")
        if state.status == "cancelled":
            return GoalLifecycleResult(state.goal_id, "cancelled", "cancelled", state.resume_cursor, "CANCEL:already_cancelled")
        return self._transition(state, "cancelled", "CANCEL")

    def resume(self, goal_id: str) -> GoalLifecycleResult:
        state = self._goal_store.load(goal_id)
        if state.status == "cancelled":
            raise ValueError("cancelled goal cannot be resumed")
        if state.status == "complete":
            raise ValueError("completed goal cannot be resumed")
        if state.status != "paused":
            raise ValueError(f"only paused goals can be explicitly resumed: {state.status}")
        if state.resume_cursor is None:
            raise ValueError("paused goal has no resume cursor")
        return self._transition(state, "in_progress", "RESUME_REQUESTED")

    def _transition(self, state: PersistentGoalState, status: str, event: str) -> GoalLifecycleResult:
        updated = replace(
            state,
            status=status,
            events=state.events + (event,),
        )
        self._goal_store.save(updated)
        return GoalLifecycleResult(
            goal_id=state.goal_id,
            previous_status=state.status,
            status=status,
            resume_cursor=state.resume_cursor,
            event=event,
        )
