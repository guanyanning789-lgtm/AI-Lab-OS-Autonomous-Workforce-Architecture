from __future__ import annotations

import pytest

from ai_lab_os.goal_lifecycle_service import GoalLifecycleService
from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState
from ai_lab_os.recovery_policy import RecoveryAction, decide_recovery


def _save_unfinished(store: JsonGoalStore, *, goal_id: str = "goal-life") -> None:
    store.save(PersistentGoalState(
        goal_id=goal_id,
        status="in_progress",
        plan={"goal_id": goal_id, "planner_version": "test", "tasks": []},
        tasks=(PersistentTaskState("task-1", status="ready", attempts=0),),
        resume_cursor="task-1",
        events=("RUNNING:task-1:attempt=0",),
    ))


def test_pause_is_durable_and_background_recovery_is_disabled(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_unfinished(store)
    lifecycle = GoalLifecycleService(store)

    result = lifecycle.pause("goal-life")
    saved = store.load("goal-life")
    decision = decide_recovery(saved)

    assert result.previous_status == "in_progress"
    assert result.status == "paused"
    assert saved.status == "paused"
    assert saved.resume_cursor == "task-1"
    assert saved.events[-1] == "PAUSE"
    assert decision.action is RecoveryAction.NONE
    assert decision.safe_to_continue is False


def test_resume_only_reenables_paused_goal_for_bounded_recovery(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_unfinished(store)
    lifecycle = GoalLifecycleService(store)
    lifecycle.pause("goal-life")

    result = lifecycle.resume("goal-life")
    saved = store.load("goal-life")
    decision = decide_recovery(saved)

    assert result.previous_status == "paused"
    assert saved.status == "in_progress"
    assert saved.events[-1] == "RESUME_REQUESTED"
    assert decision.action is RecoveryAction.RESUME
    assert decision.safe_to_continue is True


def test_cancel_is_terminal_for_background_recovery_and_cannot_resume(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_unfinished(store)
    lifecycle = GoalLifecycleService(store)

    lifecycle.cancel("goal-life")
    saved = store.load("goal-life")

    assert saved.status == "cancelled"
    assert saved.events[-1] == "CANCEL"
    assert decide_recovery(saved).action is RecoveryAction.NONE
    with pytest.raises(ValueError, match="cancelled goal cannot be resumed"):
        lifecycle.resume("goal-life")


def test_completed_goal_rejects_pause_and_cancel(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    store.save(PersistentGoalState(
        goal_id="done",
        status="complete",
        plan={"goal_id": "done", "planner_version": "test", "tasks": []},
        tasks=(),
        resume_cursor=None,
        events=("GOAL_COMPLETE",),
    ))
    lifecycle = GoalLifecycleService(store)

    with pytest.raises(ValueError, match="completed goal cannot be paused"):
        lifecycle.pause("done")
    with pytest.raises(ValueError, match="completed goal cannot be cancelled"):
        lifecycle.cancel("done")
