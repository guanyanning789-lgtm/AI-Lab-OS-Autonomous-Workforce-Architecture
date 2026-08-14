from __future__ import annotations

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus, run_supervisor_loop
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def _plan() -> TaskPlanContract:
    task = PlannedTask(
        task_id="goal-history-runtime-task-001",
        goal_id="goal-history-runtime",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Research and verify.",
        agent=AgentKind.RESEARCH,
        metadata={"skill_id": "research-code-verify"},
    )
    return TaskPlanContract(goal_id="goal-history-runtime", tasks=(task,))


def test_supervisor_records_terminal_history(tmp_path) -> None:
    goal_store = JsonGoalStore(tmp_path / "goals.json")
    history = JsonExecutionHistory(tmp_path / "history.jsonl")

    result = run_supervisor_loop(
        _plan(),
        lambda task: TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok"),
        goal_store=goal_store,
        history_store=history,
    )

    assert result.status == "complete"
    records = history.list(goal_id="goal-history-runtime")
    assert len(records) == 1
    assert records[0].skill_id == "research-code-verify"
    assert records[0].status == "complete"
    assert records[0].completed_tasks == ("goal-history-runtime-task-001",)


def test_supervisor_without_history_store_remains_backward_compatible(tmp_path) -> None:
    goal_store = JsonGoalStore(tmp_path / "goals.json")
    result = run_supervisor_loop(
        _plan(),
        lambda task: TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok"),
        goal_store=goal_store,
    )
    assert result.status == "complete"
