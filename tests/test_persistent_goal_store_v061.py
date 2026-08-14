from __future__ import annotations

import json
from dataclasses import replace

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def _plan() -> TaskPlanContract:
    first = PlannedTask(
        task_id="goal-1-task-1",
        goal_id="goal-1",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Research first.",
        agent=AgentKind.RESEARCH,
    )
    second = PlannedTask(
        task_id="goal-1-task-2",
        goal_id="goal-1",
        sequence=2,
        kind=PlannedTaskKind.VERIFY,
        description="Verify second.",
        agent=AgentKind.COMPUTER,
        depends_on=(first.task_id,),
    )
    return TaskPlanContract(goal_id="goal-1", tasks=(first, second))


def test_persistent_goal_state_from_plan_initializes_resume_cursor() -> None:
    state = PersistentGoalState.from_plan(_plan())
    assert state.goal_id == "goal-1"
    assert state.status == "pending"
    assert state.resume_cursor == "goal-1-task-1"
    assert [task.status for task in state.tasks] == ["pending", "pending"]


def test_json_goal_store_round_trips_state(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    state = PersistentGoalState.from_plan(_plan())
    state = replace(
        state,
        status="running",
        cycles=2,
        resume_cursor="goal-1-task-2",
        events=("RUNNING:goal-1-task-1", "COMPLETE:goal-1-task-1"),
        tasks=(
            PersistentTaskState("goal-1-task-1", status="complete", attempts=1, evidence=("source-a",)),
            PersistentTaskState("goal-1-task-2", status="pending"),
        ),
    )

    store.save(state)
    loaded = store.load("goal-1")

    assert loaded.status == "running"
    assert loaded.cycles == 2
    assert loaded.resume_cursor == "goal-1-task-2"
    assert loaded.tasks[0].status == "complete"
    assert loaded.tasks[0].attempts == 1
    assert loaded.tasks[0].evidence == ("source-a",)
    assert loaded.events[-1] == "COMPLETE:goal-1-task-1"


def test_json_goal_store_updates_existing_goal_atomically(tmp_path) -> None:
    path = tmp_path / "goals.json"
    store = JsonGoalStore(path)
    state = PersistentGoalState.from_plan(_plan())
    store.save(state)
    store.save(replace(state, status="complete", resume_cursor=None))

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert list(raw) == ["goal-1"]
    assert raw["goal-1"]["status"] == "complete"
    assert raw["goal-1"]["resume_cursor"] is None
    assert not (tmp_path / "goals.json.tmp").exists()


def test_json_goal_store_lists_sorted_goals(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    first = PersistentGoalState.from_plan(_plan())
    second_plan = TaskPlanContract(
        goal_id="goal-0",
        tasks=(
            PlannedTask(
                task_id="goal-0-task-1",
                goal_id="goal-0",
                sequence=1,
                kind=PlannedTaskKind.ANALYZE,
                description="Analyze.",
                agent=AgentKind.RESEARCH,
            ),
        ),
    )
    store.save(first)
    store.save(PersistentGoalState.from_plan(second_plan))

    assert [state.goal_id for state in store.list()] == ["goal-0", "goal-1"]


def test_json_goal_store_missing_goal_fails_closed(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    with pytest.raises(LookupError, match="persistent goal not found: missing"):
        store.load("missing")
