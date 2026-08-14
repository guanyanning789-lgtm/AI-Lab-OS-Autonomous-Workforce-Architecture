from __future__ import annotations

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.supervisor_loop import (
    SupervisorPolicy,
    TaskExecutionResult,
    TaskExecutionStatus,
    run_supervisor_loop,
)
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def _plan() -> TaskPlanContract:
    first = PlannedTask(
        task_id="goal-v062-task-001",
        goal_id="goal-v062",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Research first.",
        agent=AgentKind.RESEARCH,
    )
    second = PlannedTask(
        task_id="goal-v062-task-002",
        goal_id="goal-v062",
        sequence=2,
        kind=PlannedTaskKind.VERIFY,
        description="Verify second.",
        agent=AgentKind.CODING,
        depends_on=(first.task_id,),
    )
    return TaskPlanContract(goal_id="goal-v062", tasks=(first, second))


def test_supervisor_persists_retry_attempts_and_completion(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    calls: dict[str, int] = {}

    def executor(task: PlannedTask) -> TaskExecutionResult:
        calls[task.task_id] = calls.get(task.task_id, 0) + 1
        if task.sequence == 1 and calls[task.task_id] == 1:
            return TaskExecutionResult(TaskExecutionStatus.FAILED, "temporary research failure")
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = run_supervisor_loop(
        _plan(),
        executor,
        policy=SupervisorPolicy(max_attempts_per_task=2),
        goal_store=store,
    )

    assert result.status == "complete"
    saved = store.load("goal-v062")
    assert saved.status == "complete"
    assert saved.resume_cursor is None
    assert saved.cycles == 3
    assert saved.schema_version == "0.6.2"
    assert [task.status for task in saved.tasks] == ["complete", "complete"]
    assert [task.attempts for task in saved.tasks] == [2, 1]
    assert any(event.startswith("FAILED:goal-v062-task-001") for event in saved.events)
    assert "RETRY:goal-v062-task-001" in saved.events
    assert saved.events[-1] == "GOAL_COMPLETE"


def test_supervisor_persists_replan_cursor_and_error(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task: PlannedTask) -> TaskExecutionResult:
        return TaskExecutionResult(TaskExecutionStatus.NEEDS_REPLAN, "needs a new plan")

    result = run_supervisor_loop(_plan(), executor, goal_store=store)

    assert result.status == "replan_required"
    saved = store.load("goal-v062")
    assert saved.status == "replan_required"
    assert saved.resume_cursor == "goal-v062-task-001"
    assert saved.tasks[0].status == "replan"
    assert saved.tasks[0].attempts == 1
    assert "needs a new plan" in saved.tasks[0].message
    assert "REPLAN:goal-v062-task-001" in saved.events
    assert saved.events[-1] == "REPLAN_REQUIRED:goal-v062-task-001"


def test_supervisor_without_store_remains_backward_compatible() -> None:
    result = run_supervisor_loop(
        _plan(),
        lambda task: TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok"),
    )
    assert result.status == "complete"
    assert result.completed_tasks == (
        "goal-v062-task-001",
        "goal-v062-task-002",
    )
