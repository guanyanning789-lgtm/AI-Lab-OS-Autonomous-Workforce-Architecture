from __future__ import annotations

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
    first = PlannedTask(
        task_id="goal-resume-task-001",
        goal_id="goal-resume",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description="Complete the first durable step.",
        agent=AgentKind.CODING,
    )
    second = PlannedTask(
        task_id="goal-resume-task-002",
        goal_id="goal-resume",
        sequence=2,
        kind=PlannedTaskKind.VERIFY,
        description="Complete the second durable step.",
        agent=AgentKind.CODING,
        depends_on=(first.task_id,),
    )
    return TaskPlanContract(goal_id="goal-resume", tasks=(first, second))


def test_task_plan_round_trips_from_persisted_dict() -> None:
    plan = _plan()
    restored = TaskPlanContract.from_dict(plan.to_dict())
    assert restored == plan


def test_resume_after_restart_skips_completed_work(tmp_path) -> None:
    path = tmp_path / "goals.json"
    store = JsonGoalStore(path)
    first_process_calls: list[str] = []

    def first_process_executor(task: PlannedTask) -> TaskExecutionResult:
        first_process_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    first_result = run_supervisor_loop(
        _plan(),
        first_process_executor,
        policy=SupervisorPolicy(max_cycles=1),
        goal_store=store,
    )

    assert first_result.status == "cycle_limit"
    assert first_process_calls == ["goal-resume-task-001"]
    persisted = store.load("goal-resume")
    assert persisted.resume_cursor == "goal-resume-task-002"
    assert [task.status for task in persisted.tasks] == ["complete", "ready"]

    # Simulate a new process by constructing a fresh store instance.
    restarted_store = JsonGoalStore(path)
    second_process_calls: list[str] = []

    def second_process_executor(task: PlannedTask) -> TaskExecutionResult:
        second_process_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done after restart")

    resumed = resume_supervisor_from_store(
        "goal-resume",
        second_process_executor,
        restarted_store,
        policy=SupervisorPolicy(max_cycles=10),
    )

    assert resumed.status == "complete"
    assert second_process_calls == ["goal-resume-task-002"]
    assert "RESUME:goal-resume-task-002" in resumed.events
    assert resumed.events[-1] == "GOAL_COMPLETE"

    final = restarted_store.load("goal-resume")
    assert final.status == "complete"
    assert final.resume_cursor is None
    assert [task.status for task in final.tasks] == ["complete", "complete"]


def test_resume_recovers_persisted_running_task_as_ready(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    plan = _plan()

    calls = 0

    def interrupted_executor(task: PlannedTask) -> TaskExecutionResult:
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt("simulated process death")

    # KeyboardInterrupt is intentionally outside Exception and simulates a hard stop
    # after RUNNING was already persisted.
    try:
        run_supervisor_loop(plan, interrupted_executor, goal_store=store)
    except KeyboardInterrupt:
        pass

    persisted = store.load("goal-resume")
    assert persisted.tasks[0].status == "running"
    assert persisted.resume_cursor == "goal-resume-task-001"

    resumed_calls: list[str] = []

    def resumed_executor(task: PlannedTask) -> TaskExecutionResult:
        resumed_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "recovered")

    result = resume_supervisor_from_store(
        "goal-resume",
        resumed_executor,
        JsonGoalStore(store.path),
    )

    assert result.status == "complete"
    assert resumed_calls == ["goal-resume-task-001", "goal-resume-task-002"]
