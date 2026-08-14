from __future__ import annotations

from dataclasses import replace

from ai_lab_os.persistent_goal_store import PersistentGoalState, PersistentTaskState
from ai_lab_os.recovery_policy import RecoveryAction, RecoveryPolicyConfig, decide_recovery


def _state(*, status: str = "in_progress", task_status: str = "ready", attempts: int = 0, cycles: int = 1) -> PersistentGoalState:
    return PersistentGoalState(
        goal_id="goal-v071",
        status=status,
        plan={"goal_id": "goal-v071", "tasks": []},
        tasks=(PersistentTaskState("task-1", status=task_status, attempts=attempts),),
        resume_cursor="task-1",
        cycles=cycles,
    )


def test_complete_goal_requires_no_recovery() -> None:
    decision = decide_recovery(replace(_state(), status="complete", resume_cursor=None))
    assert decision.action is RecoveryAction.NONE
    assert decision.safe_to_continue is False


def test_in_progress_goal_resumes_from_cursor() -> None:
    decision = decide_recovery(_state(status="in_progress", task_status="ready"))
    assert decision.action is RecoveryAction.RESUME
    assert decision.task_id == "task-1"
    assert decision.safe_to_continue is True


def test_failed_task_escalates_retry_repair_replan_by_attempt_budget() -> None:
    config = RecoveryPolicyConfig(max_retry_attempts=2, max_repair_attempts=3)

    retry = decide_recovery(_state(status="failed", task_status="failed", attempts=1), config=config)
    repair = decide_recovery(_state(status="failed", task_status="failed", attempts=2), config=config)
    replan = decide_recovery(_state(status="failed", task_status="failed", attempts=3), config=config)

    assert retry.action is RecoveryAction.RETRY
    assert retry.safe_to_continue is True
    assert repair.action is RecoveryAction.REPAIR
    assert repair.safe_to_continue is True
    assert replan.action is RecoveryAction.REPLAN
    assert replan.safe_to_continue is False


def test_replan_required_stays_replan() -> None:
    decision = decide_recovery(_state(status="replan_required", task_status="replan", attempts=2))
    assert decision.action is RecoveryAction.REPLAN
    assert decision.safe_to_continue is False


def test_blocked_goal_escalates() -> None:
    decision = decide_recovery(_state(status="blocked"))
    assert decision.action is RecoveryAction.ESCALATE
    assert decision.safe_to_continue is False


def test_unknown_resume_cursor_escalates_fail_closed() -> None:
    state = replace(_state(), resume_cursor="missing-task")
    decision = decide_recovery(state)
    assert decision.action is RecoveryAction.ESCALATE
    assert "unknown task" in decision.reason


def test_cycle_budget_exhaustion_escalates_before_resume() -> None:
    config = RecoveryPolicyConfig(max_total_cycles=5)
    decision = decide_recovery(_state(cycles=5), config=config)
    assert decision.action is RecoveryAction.ESCALATE
    assert "cycle budget" in decision.reason
