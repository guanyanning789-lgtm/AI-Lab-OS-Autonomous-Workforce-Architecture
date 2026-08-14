from __future__ import annotations

import json

import pytest

from ai_lab_os.goal_contract import GoalContract, GoalPriority
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract, plan_goal, write_task_plan
from ai_lab_os.models import AgentKind


def _goal() -> GoalContract:
    return GoalContract(
        goal_id="goal-0001",
        natural_language_goal="Add a health endpoint and verify it",
        success_criteria=(
            "The endpoint returns healthy status",
            "All configured tests pass",
        ),
        constraints=("Make the smallest safe change",),
        priority=GoalPriority.HIGH,
    )


def test_plan_goal_creates_explicit_three_step_plan() -> None:
    plan = plan_goal(_goal())

    assert plan.goal_id == "goal-0001"
    assert plan.planner_version == "v0.3.2"
    assert [task.sequence for task in plan.tasks] == [1, 2, 3]
    assert [task.kind for task in plan.tasks] == [
        PlannedTaskKind.ANALYZE,
        PlannedTaskKind.IMPLEMENT,
        PlannedTaskKind.VERIFY,
    ]
    assert [task.task_id for task in plan.tasks] == [
        "goal-0001-task-001",
        "goal-0001-task-002",
        "goal-0001-task-003",
    ]
    assert plan.tasks[1].depends_on == ("goal-0001-task-001",)
    assert plan.tasks[2].depends_on == ("goal-0001-task-002",)
    assert all(task.agent is AgentKind.CODING for task in plan.tasks)


def test_plan_goal_preserves_goal_success_criteria_for_implementation_and_verification() -> None:
    goal = _goal()
    plan = plan_goal(goal)

    assert plan.tasks[1].success_criteria == goal.success_criteria
    assert plan.tasks[2].success_criteria == goal.success_criteria
    assert goal.natural_language_goal in plan.tasks[0].description
    assert goal.constraints[0] in plan.tasks[0].description


def test_task_plan_rejects_unknown_dependency() -> None:
    task = PlannedTask(
        task_id="goal-1-task-001",
        goal_id="goal-1",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Analyze",
        agent=AgentKind.CODING,
        depends_on=("missing",),
    )

    with pytest.raises(ValueError, match="unknown tasks"):
        TaskPlanContract(goal_id="goal-1", tasks=(task,))


def test_task_plan_rejects_dependency_on_later_task() -> None:
    first = PlannedTask(
        task_id="goal-1-task-001",
        goal_id="goal-1",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Analyze",
        agent=AgentKind.CODING,
        depends_on=("goal-1-task-002",),
    )
    second = PlannedTask(
        task_id="goal-1-task-002",
        goal_id="goal-1",
        sequence=2,
        kind=PlannedTaskKind.IMPLEMENT,
        description="Implement",
        agent=AgentKind.CODING,
    )

    with pytest.raises(ValueError, match="earlier tasks"):
        TaskPlanContract(goal_id="goal-1", tasks=(first, second))


def test_write_task_plan_serializes_stable_contract(tmp_path) -> None:
    destination = tmp_path / "plans" / "goal-0001.json"
    write_task_plan(destination, plan_goal(_goal()))

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["goal_id"] == "goal-0001"
    assert payload["planner_version"] == "v0.3.2"
    assert len(payload["tasks"]) == 3
    assert payload["tasks"][2]["depends_on"] == ["goal-0001-task-002"]
