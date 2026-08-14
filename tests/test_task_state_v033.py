from __future__ import annotations

import pytest

from ai_lab_os.goal_contract import GoalContract
from ai_lab_os.task_planner import plan_goal
from ai_lab_os.task_state import PlanRuntimeState, TaskLifecycleStatus


def _runtime() -> PlanRuntimeState:
    goal = GoalContract(
        goal_id="goal-state-1",
        natural_language_goal="Add and verify a health endpoint",
        success_criteria=("All tests pass",),
    )
    return PlanRuntimeState.from_plan(plan_goal(goal))


def test_first_task_becomes_ready_and_dependencies_unlock_in_order() -> None:
    runtime = _runtime()
    first, second, third = [task.task_id for task in runtime.plan.tasks]

    assert runtime.tasks[first].status is TaskLifecycleStatus.READY
    assert runtime.tasks[second].status is TaskLifecycleStatus.PENDING
    assert runtime.tasks[third].status is TaskLifecycleStatus.PENDING

    runtime.tasks[first].transition(TaskLifecycleStatus.RUNNING)
    runtime.mark_complete(first)
    assert runtime.tasks[second].status is TaskLifecycleStatus.READY

    runtime.tasks[second].transition(TaskLifecycleStatus.RUNNING)
    runtime.mark_complete(second)
    assert runtime.tasks[third].status is TaskLifecycleStatus.READY


def test_invalid_transition_is_rejected() -> None:
    runtime = _runtime()
    first = runtime.plan.tasks[0].task_id

    with pytest.raises(ValueError, match="invalid task transition"):
        runtime.tasks[first].transition(TaskLifecycleStatus.COMPLETE)


def test_failure_can_retry_and_increment_attempts() -> None:
    runtime = _runtime()
    first = runtime.plan.tasks[0].task_id
    state = runtime.tasks[first]

    state.transition(TaskLifecycleStatus.RUNNING)
    runtime.mark_failed(first, "temporary failure")
    assert state.status is TaskLifecycleStatus.FAILED
    assert state.last_error == "temporary failure"
    assert state.attempts == 1

    runtime.request_recovery(first, TaskLifecycleStatus.RETRY)
    assert state.status is TaskLifecycleStatus.READY
    assert state.last_error is None

    state.transition(TaskLifecycleStatus.RUNNING)
    assert state.attempts == 2


def test_failure_can_request_repair_or_replan() -> None:
    repair_runtime = _runtime()
    first = repair_runtime.plan.tasks[0].task_id
    repair_runtime.tasks[first].transition(TaskLifecycleStatus.RUNNING)
    repair_runtime.mark_failed(first, "needs repair")
    repair_runtime.request_recovery(first, TaskLifecycleStatus.REPAIR)
    assert repair_runtime.tasks[first].status is TaskLifecycleStatus.READY
    assert TaskLifecycleStatus.REPAIR in repair_runtime.tasks[first].history

    replan_runtime = _runtime()
    first = replan_runtime.plan.tasks[0].task_id
    replan_runtime.tasks[first].transition(TaskLifecycleStatus.RUNNING)
    replan_runtime.mark_failed(first, "plan is wrong")
    replan_runtime.request_recovery(first, TaskLifecycleStatus.REPLAN)
    assert replan_runtime.tasks[first].status is TaskLifecycleStatus.REPLAN


def test_all_complete_only_after_every_task_finishes() -> None:
    runtime = _runtime()
    assert runtime.all_complete() is False

    while (task_id := runtime.next_ready_task_id()) is not None:
        runtime.tasks[task_id].transition(TaskLifecycleStatus.RUNNING)
        runtime.mark_complete(task_id)

    assert runtime.all_complete() is True
