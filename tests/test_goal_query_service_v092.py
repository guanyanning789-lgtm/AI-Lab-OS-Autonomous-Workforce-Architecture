from __future__ import annotations

import pytest

from ai_lab_os.goal_query_service import GoalQueryService
from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState


def _state(goal_id: str = "goal-q", status: str = "in_progress") -> PersistentGoalState:
    return PersistentGoalState(
        goal_id=goal_id,
        status=status,
        plan={"goal_id": goal_id, "tasks": []},
        tasks=(
            PersistentTaskState("task-1", status="complete", attempts=1, evidence=("proof",)),
            PersistentTaskState("task-2", status="failed", attempts=2, message="tests failed"),
        ),
        resume_cursor="task-2",
        cycles=3,
        events=(
            "RUNNING:task-1:attempt=1",
            "COMPLETE:task-1",
            "FAILED:task-2:tests failed",
        ),
    )


def test_get_goal_shapes_progress_status_events_and_last_error(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    store.save(_state())
    service = GoalQueryService(store)

    result = service.get_goal("goal-q")

    assert result.goal_id == "goal-q"
    assert result.status == "in_progress"
    assert result.resume_cursor == "task-2"
    assert result.cycles == 3
    assert result.completed_tasks == 1
    assert result.total_tasks == 2
    assert result.progress_percent == 50
    assert result.last_error == "tests failed"
    assert result.tasks[0].evidence == ("proof",)
    assert result.events[-1] == "FAILED:task-2:tests failed"


def test_get_events_supports_incremental_cursor(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    store.save(_state())
    service = GoalQueryService(store)

    assert service.get_events("goal-q", after=1) == (
        "COMPLETE:task-1",
        "FAILED:task-2:tests failed",
    )
    with pytest.raises(ValueError, match="after must be >= 0"):
        service.get_events("goal-q", after=-1)


def test_list_goals_can_filter_by_status(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    store.save(_state("goal-a", "in_progress"))
    store.save(_state("goal-b", "complete"))
    service = GoalQueryService(store)

    assert [item.goal_id for item in service.list_goals()] == ["goal-a", "goal-b"]
    assert [item.goal_id for item in service.list_goals(status="complete")] == ["goal-b"]
    with pytest.raises(ValueError, match="status filter cannot be blank"):
        service.list_goals(status="   ")


def test_missing_goal_propagates_lookup_error(tmp_path) -> None:
    service = GoalQueryService(JsonGoalStore(tmp_path / "goals.json"))
    with pytest.raises(LookupError, match="persistent goal not found"):
        service.get_goal("missing")
