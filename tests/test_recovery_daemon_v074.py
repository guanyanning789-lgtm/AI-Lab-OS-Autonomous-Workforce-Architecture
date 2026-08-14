from __future__ import annotations

from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState
from ai_lab_os.recovery_daemon import RecoveryDaemonConfig, run_recovery_daemon, scan_once
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract
from ai_lab_os.models import AgentKind


def _plan(goal_id: str) -> TaskPlanContract:
    return TaskPlanContract(
        goal_id=goal_id,
        tasks=(
            PlannedTask(
                task_id=f"{goal_id}-task-1",
                goal_id=goal_id,
                sequence=1,
                kind=PlannedTaskKind.VERIFY,
                description="Verify safely.",
                agent=AgentKind.CODING,
            ),
        ),
    )


def _save_resumable(store: JsonGoalStore, goal_id: str) -> None:
    plan = _plan(goal_id)
    store.save(
        PersistentGoalState(
            goal_id=goal_id,
            status="in_progress",
            plan=plan.to_dict(),
            tasks=(PersistentTaskState(f"{goal_id}-task-1", status="ready"),),
            resume_cursor=f"{goal_id}-task-1",
        )
    )


def _save_complete(store: JsonGoalStore, goal_id: str) -> None:
    plan = _plan(goal_id)
    store.save(
        PersistentGoalState(
            goal_id=goal_id,
            status="complete",
            plan=plan.to_dict(),
            tasks=(PersistentTaskState(f"{goal_id}-task-1", status="complete", attempts=1),),
            resume_cursor=None,
        )
    )


def test_scan_once_resumes_unfinished_and_skips_complete(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_resumable(store, "goal-a")
    _save_complete(store, "goal-b")
    calls: list[str] = []

    def executor(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    report = scan_once(executor, store)
    assert report.total_goals == 2
    assert report.completed_goals == 1
    assert report.actionable_goals == 1
    assert calls == ["goal-a-task-1"]
    assert store.load("goal-a").status == "complete"


def test_daemon_stops_when_idle_after_recovery(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_resumable(store, "goal-a")
    sleeps: list[float] = []

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    reports = run_recovery_daemon(
        executor,
        store,
        config=RecoveryDaemonConfig(poll_seconds=0.01, max_scans=5, stop_when_idle=True),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )
    assert len(reports) == 2
    assert reports[0].actionable_goals == 1
    assert reports[1].idle is True
    assert sleeps == [0.01]


def test_daemon_respects_max_scans(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_complete(store, "goal-a")
    sleeps: list[float] = []

    reports = run_recovery_daemon(
        lambda task: TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok"),
        store,
        config=RecoveryDaemonConfig(poll_seconds=0.25, max_scans=3, stop_when_idle=False),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )
    assert len(reports) == 3
    assert [report.scan_number for report in reports] == [1, 2, 3]
    assert sleeps == [0.25, 0.25]


def test_daemon_config_rejects_invalid_values() -> None:
    import pytest

    with pytest.raises(ValueError, match="poll_seconds"):
        RecoveryDaemonConfig(poll_seconds=0)
    with pytest.raises(ValueError, match="max_scans"):
        RecoveryDaemonConfig(max_scans=0)
