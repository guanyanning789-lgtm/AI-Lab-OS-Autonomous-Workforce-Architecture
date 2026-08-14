from __future__ import annotations

from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState
from ai_lab_os.recovery_policy import RecoveryAction
from ai_lab_os.recovery_runner import recover_all, recover_goal
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind, TaskPlanContract
from ai_lab_os.models import AgentKind


def _plan(goal_id: str) -> TaskPlanContract:
    first = f"{goal_id}-1"
    second = f"{goal_id}-2"
    return TaskPlanContract(
        goal_id=goal_id,
        tasks=(
            PlannedTask(first, goal_id, 1, PlannedTaskKind.ANALYZE, "first", AgentKind.RESEARCH),
            PlannedTask(second, goal_id, 2, PlannedTaskKind.VERIFY, "second", AgentKind.CODING, depends_on=(first,)),
        ),
    )


def _save_resume_state(store: JsonGoalStore, goal_id: str) -> None:
    plan = _plan(goal_id)
    store.save(
        PersistentGoalState(
            goal_id=goal_id,
            status="in_progress",
            plan=plan.to_dict(),
            tasks=(
                PersistentTaskState(plan.tasks[0].task_id, status="complete", attempts=1),
                PersistentTaskState(plan.tasks[1].task_id, status="ready", attempts=0),
            ),
            resume_cursor=plan.tasks[1].task_id,
            cycles=1,
            events=(f"COMPLETE:{plan.tasks[0].task_id}",),
            schema_version="0.6.2",
        )
    )


def test_recovery_runner_resumes_unfinished_goal(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_resume_state(store, "goal-resume")
    calls: list[str] = []

    def executor(task: PlannedTask) -> TaskExecutionResult:
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = recover_goal("goal-resume", executor, store)

    assert result.decision.action is RecoveryAction.RESUME
    assert result.status == "complete"
    assert calls == ["goal-resume-2"]
    assert store.load("goal-resume").status == "complete"


def test_recovery_runner_does_not_execute_complete_goal(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    plan = _plan("goal-complete")
    store.save(
        PersistentGoalState(
            goal_id=plan.goal_id,
            status="complete",
            plan=plan.to_dict(),
            tasks=tuple(PersistentTaskState(task.task_id, status="complete", attempts=1) for task in plan.tasks),
            resume_cursor=None,
            cycles=2,
            schema_version="0.6.2",
        )
    )
    called = False

    def executor(task: PlannedTask) -> TaskExecutionResult:
        nonlocal called
        called = True
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = recover_goal(plan.goal_id, executor, store)
    assert result.status == "no_action"
    assert called is False


def test_recovery_runner_reports_replan_without_handler(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    plan = _plan("goal-replan")
    store.save(
        PersistentGoalState(
            goal_id=plan.goal_id,
            status="replan_required",
            plan=plan.to_dict(),
            tasks=(
                PersistentTaskState(plan.tasks[0].task_id, status="complete", attempts=1),
                PersistentTaskState(plan.tasks[1].task_id, status="replan", attempts=3, message="failed"),
            ),
            resume_cursor=plan.tasks[1].task_id,
            cycles=4,
            schema_version="0.6.2",
        )
    )

    result = recover_goal(plan.goal_id, lambda task: TaskExecutionResult(TaskExecutionStatus.SUCCESS), store)
    assert result.decision.action is RecoveryAction.REPLAN
    assert result.status == "replan_required"
    assert result.supervisor_result is None


def test_recover_all_handles_complete_and_resumable_goals(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    _save_resume_state(store, "b-resume")
    plan = _plan("a-complete")
    store.save(
        PersistentGoalState(
            goal_id=plan.goal_id,
            status="complete",
            plan=plan.to_dict(),
            tasks=tuple(PersistentTaskState(task.task_id, status="complete", attempts=1) for task in plan.tasks),
            resume_cursor=None,
            cycles=2,
            schema_version="0.6.2",
        )
    )

    calls: list[str] = []
    results = recover_all(
        lambda task: (calls.append(task.task_id) or TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")),
        store,
    )

    assert [result.goal_id for result in results] == ["a-complete", "b-resume"]
    assert [result.status for result in results] == ["no_action", "complete"]
    assert calls == ["b-resume-2"]
