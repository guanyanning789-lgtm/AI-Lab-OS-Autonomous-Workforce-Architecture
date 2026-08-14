from __future__ import annotations

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.supervisor_loop import (
    SupervisorPolicy,
    TaskExecutionResult,
    TaskExecutionStatus,
    resume_supervisor_from_store,
    run_supervisor_loop,
)
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract


def _plan() -> TaskPlanContract:
    tasks = (
        PlannedTask(
            task_id="goal-v065-task-001",
            goal_id="goal-v065",
            sequence=1,
            kind=PlannedTaskKind.ANALYZE,
            description="Research fixture behavior.",
            agent=AgentKind.RESEARCH,
            metadata={"skill_id": "restart-resume-test"},
        ),
        PlannedTask(
            task_id="goal-v065-task-002",
            goal_id="goal-v065",
            sequence=2,
            kind=PlannedTaskKind.VERIFY,
            description="Verify code.",
            agent=AgentKind.CODING,
            depends_on=("goal-v065-task-001",),
            metadata={"skill_id": "restart-resume-test"},
        ),
        PlannedTask(
            task_id="goal-v065-task-003",
            goal_id="goal-v065",
            sequence=3,
            kind=PlannedTaskKind.VERIFY,
            description="Verify computer runtime.",
            agent=AgentKind.COMPUTER,
            depends_on=("goal-v065-task-002",),
            metadata={"skill_id": "restart-resume-test"},
        ),
    )
    return TaskPlanContract(goal_id="goal-v065", tasks=tasks)


def test_restart_resume_skips_completed_work_and_reaches_goal_complete(tmp_path) -> None:
    state_path = tmp_path / "goals.json"
    history_path = tmp_path / "history.jsonl"
    phase1_calls: list[str] = []

    def phase1_executor(task: PlannedTask) -> TaskExecutionResult:
        phase1_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    phase1 = run_supervisor_loop(
        _plan(),
        phase1_executor,
        policy=SupervisorPolicy(max_cycles=1),
        goal_store=JsonGoalStore(state_path),
        history_store=JsonExecutionHistory(history_path),
    )

    assert phase1.status == "cycle_limit"
    assert phase1_calls == ["goal-v065-task-001"]
    persisted = JsonGoalStore(state_path).load("goal-v065")
    assert persisted.tasks[0].status == "complete"
    assert persisted.resume_cursor == "goal-v065-task-002"

    phase2_calls: list[str] = []

    def phase2_executor(task: PlannedTask) -> TaskExecutionResult:
        phase2_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    phase2 = resume_supervisor_from_store(
        "goal-v065",
        phase2_executor,
        JsonGoalStore(state_path),
        policy=SupervisorPolicy(max_cycles=50),
        history_store=JsonExecutionHistory(history_path),
    )

    assert phase2.status == "complete"
    assert phase2_calls == ["goal-v065-task-002", "goal-v065-task-003"]
    assert "GOAL_COMPLETE" in phase2.events
    assert not any(
        event.startswith("RUNNING:goal-v065-task-001:")
        for event in phase2.events[phase1.cycles * 2 + 1 :]
    )

    final_state = JsonGoalStore(state_path).load("goal-v065")
    assert final_state.status == "complete"
    assert final_state.resume_cursor is None
    assert all(task.status == "complete" for task in final_state.tasks)

    history = JsonExecutionHistory(history_path)
    records = history.list(goal_id="goal-v065")
    assert [record.status for record in records] == ["cycle_limit", "complete"]
    assert history.latest(goal_id="goal-v065").skill_id == "restart-resume-test"
