from __future__ import annotations

from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_daemon import RecoveryDaemonConfig, run_recovery_daemon
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus, run_supervisor_loop
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract
from ai_lab_os.models import AgentKind


def _plan() -> TaskPlanContract:
    return TaskPlanContract(
        goal_id="v075-auto-recovery",
        tasks=(
            PlannedTask("task-1", "v075-auto-recovery", 1, PlannedTaskKind.ANALYZE, "Analyze.", AgentKind.RESEARCH),
            PlannedTask("task-2", "v075-auto-recovery", 2, PlannedTaskKind.VERIFY, "Verify code.", AgentKind.CODING, depends_on=("task-1",)),
            PlannedTask("task-3", "v075-auto-recovery", 3, PlannedTaskKind.VERIFY, "Verify computer.", AgentKind.COMPUTER, depends_on=("task-2",)),
        ),
    )


def test_daemon_discovers_and_completes_persisted_goal_without_manual_resume(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    plan = _plan()
    phase1_calls: list[str] = []

    def phase1_executor(task: PlannedTask) -> TaskExecutionResult:
        phase1_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    first = run_supervisor_loop(
        plan,
        phase1_executor,
        policy=SupervisorPolicy(max_cycles=1),
        goal_store=store,
    )
    assert first.status == "cycle_limit"
    assert phase1_calls == ["task-1"]
    assert store.load(plan.goal_id).resume_cursor == "task-2"

    daemon_calls: list[str] = []

    def daemon_executor(task: PlannedTask) -> TaskExecutionResult:
        daemon_calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    reports = run_recovery_daemon(
        daemon_executor,
        store,
        config=RecoveryDaemonConfig(poll_seconds=0.01, max_scans=1),
        supervisor_policy=SupervisorPolicy(max_cycles=50),
        sleep_fn=lambda _: None,
    )

    assert len(reports) == 1
    assert daemon_calls == ["task-2", "task-3"]
    final = store.load(plan.goal_id)
    assert final.status == "complete"
    assert final.resume_cursor is None
    result = reports[0].results[0]
    assert result.supervisor_result is not None
    assert result.supervisor_result.status == "complete"
    assert "GOAL_COMPLETE" in result.supervisor_result.events
