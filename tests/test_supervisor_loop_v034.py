from __future__ import annotations

from collections import defaultdict

from ai_lab_os.goal_contract import GoalContract
from ai_lab_os.supervisor_loop import (
    SupervisorPolicy,
    TaskExecutionResult,
    TaskExecutionStatus,
    run_supervisor_loop,
)
from ai_lab_os.task_planner import plan_goal


def _plan():
    goal = GoalContract(
        goal_id="goal-supervisor-1",
        natural_language_goal="Add and verify a health endpoint",
        success_criteria=("All tests pass",),
    )
    return plan_goal(goal)


def test_supervisor_completes_all_tasks_in_dependency_order() -> None:
    seen: list[str] = []

    def executor(task):
        seen.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = run_supervisor_loop(_plan(), executor)

    assert result.status == "complete"
    assert result.cycles == 3
    assert seen == [task.task_id for task in _plan().tasks]
    assert result.completed_tasks == tuple(seen)
    assert result.events[-1] == "GOAL_COMPLETE"


def test_supervisor_retries_a_transient_failure_then_continues() -> None:
    calls = defaultdict(int)
    first_id = _plan().tasks[0].task_id

    def executor(task):
        calls[task.task_id] += 1
        if task.task_id == first_id and calls[task.task_id] == 1:
            return TaskExecutionResult(TaskExecutionStatus.FAILED, "temporary")
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = run_supervisor_loop(
        _plan(),
        executor,
        policy=SupervisorPolicy(max_attempts_per_task=2),
    )

    assert result.status == "complete"
    assert calls[first_id] == 2
    assert f"RETRY:{first_id}" in result.events


def test_supervisor_requests_replan_after_attempt_budget_is_exhausted() -> None:
    first_id = _plan().tasks[0].task_id

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.FAILED, "still broken")

    result = run_supervisor_loop(
        _plan(),
        executor,
        policy=SupervisorPolicy(max_attempts_per_task=2),
    )

    assert result.status == "replan_required"
    assert result.failed_task_id == first_id
    assert result.cycles == 2
    assert f"REPLAN:{first_id}" in result.events


def test_supervisor_honors_explicit_replan_signal() -> None:
    first_id = _plan().tasks[0].task_id

    def executor(task):
        return TaskExecutionResult(
            TaskExecutionStatus.NEEDS_REPLAN,
            "current plan cannot satisfy constraints",
        )

    result = run_supervisor_loop(_plan(), executor)

    assert result.status == "replan_required"
    assert result.failed_task_id == first_id
    assert result.cycles == 1


def test_supervisor_converts_executor_exception_into_recovery() -> None:
    calls = defaultdict(int)
    first_id = _plan().tasks[0].task_id

    def executor(task):
        calls[task.task_id] += 1
        if task.task_id == first_id and calls[task.task_id] == 1:
            raise RuntimeError("boom")
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = run_supervisor_loop(_plan(), executor)

    assert result.status == "complete"
    assert calls[first_id] == 2
    assert any(event.startswith(f"FAILED:{first_id}:executor exception") for event in result.events)
