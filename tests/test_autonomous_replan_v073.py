from __future__ import annotations

from dataclasses import replace

import pytest

from ai_lab_os.autonomous_replan import build_bounded_replan, validate_replan_candidate
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import PersistentGoalState, PersistentTaskState
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def _plan() -> TaskPlanContract:
    return TaskPlanContract(
        goal_id="goal-r",
        tasks=(
            PlannedTask("task-1", "goal-r", 1, PlannedTaskKind.ANALYZE, "Research safely.", AgentKind.RESEARCH),
            PlannedTask("task-2", "goal-r", 2, PlannedTaskKind.IMPLEMENT, "Implement safely.", AgentKind.CODING, success_criteria=("tests pass",), depends_on=("task-1",)),
        ),
    )


def _state() -> PersistentGoalState:
    plan = _plan()
    return PersistentGoalState(
        goal_id=plan.goal_id,
        status="replan_required",
        plan=plan.to_dict(),
        tasks=(
            PersistentTaskState("task-1", status="complete", attempts=1),
            PersistentTaskState("task-2", status="replan", attempts=3, message="tests still fail"),
        ),
        resume_cursor="task-2",
        cycles=4,
    )


def test_bounded_replan_only_changes_failed_task_and_preserves_authority() -> None:
    result = build_bounded_replan(_state())
    before = result.original_plan
    after = result.candidate_plan
    assert result.failed_task_id == "task-2"
    assert result.changed_task_ids == ("task-2",)
    assert after.tasks[0] == before.tasks[0]
    assert after.tasks[1].agent is AgentKind.CODING
    assert after.tasks[1].depends_on == ("task-1",)
    assert after.tasks[1].success_criteria == ("tests pass",)
    assert after.tasks[1].metadata["recovery_mode"] == "replan"
    assert after.tasks[1].metadata["replan_reason"] == "tests still fail"
    assert "tests still fail" in after.tasks[1].description


def test_replan_rejects_agent_escalation() -> None:
    original = _plan()
    bad_task = replace(original.tasks[1], agent=AgentKind.COMPUTER)
    candidate = TaskPlanContract(goal_id=original.goal_id, tasks=(original.tasks[0], bad_task))
    with pytest.raises(ValueError, match="assigned agent"):
        validate_replan_candidate(original, candidate, failed_task_id="task-2")


def test_replan_rejects_dependency_rewrite() -> None:
    original = _plan()
    bad_task = replace(original.tasks[1], depends_on=())
    candidate = TaskPlanContract(goal_id=original.goal_id, tasks=(original.tasks[0], bad_task))
    with pytest.raises(ValueError, match="dependencies"):
        validate_replan_candidate(original, candidate, failed_task_id="task-2")


def test_replan_requires_known_failed_task() -> None:
    state = replace(_state(), resume_cursor="missing")
    with pytest.raises(ValueError, match="not present"):
        build_bounded_replan(state)
