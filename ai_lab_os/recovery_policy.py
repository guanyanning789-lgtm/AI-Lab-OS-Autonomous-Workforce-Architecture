from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_lab_os.persistent_goal_store import PersistentGoalState, PersistentTaskState


class RecoveryAction(str, Enum):
    NONE = "none"
    RESUME = "resume"
    RETRY = "retry"
    REPAIR = "repair"
    REPLAN = "replan"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RecoveryPolicyConfig:
    max_retry_attempts: int = 2
    max_repair_attempts: int = 3
    max_total_cycles: int = 100

    def __post_init__(self) -> None:
        if self.max_retry_attempts < 1:
            raise ValueError("max_retry_attempts must be >= 1")
        if self.max_repair_attempts < self.max_retry_attempts:
            raise ValueError("max_repair_attempts must be >= max_retry_attempts")
        if self.max_total_cycles < 1:
            raise ValueError("max_total_cycles must be >= 1")


@dataclass(frozen=True)
class RecoveryDecision:
    goal_id: str
    action: RecoveryAction
    task_id: str | None
    reason: str
    attempts: int = 0
    safe_to_continue: bool = False


def _task_by_id(state: PersistentGoalState, task_id: str | None) -> PersistentTaskState | None:
    if task_id is None:
        return None
    return next((task for task in state.tasks if task.task_id == task_id), None)


def decide_recovery(
    state: PersistentGoalState,
    *,
    config: RecoveryPolicyConfig | None = None,
) -> RecoveryDecision:
    """Choose the next durable recovery action without performing it.

    The policy is intentionally deterministic and fail-closed. Product lifecycle
    and human-approval states are explicitly non-actionable so background
    recovery cannot silently restart user-stopped or unapproved work.
    """

    config = config or RecoveryPolicyConfig()
    status = state.status.strip().casefold()

    if status == "complete":
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.NONE,
            task_id=None,
            reason="goal is already complete",
            safe_to_continue=False,
        )

    if status in {"paused", "cancelled", "approval_required"}:
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.NONE,
            task_id=state.resume_cursor,
            reason=(
                "goal is waiting for explicit human approval; background recovery is disabled"
                if status == "approval_required"
                else f"goal lifecycle state is {status}; background recovery is disabled"
            ),
            attempts=0,
            safe_to_continue=False,
        )

    if state.cycles >= config.max_total_cycles:
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.ESCALATE,
            task_id=state.resume_cursor,
            reason="goal exceeded the autonomous recovery cycle budget",
            safe_to_continue=False,
        )

    task = _task_by_id(state, state.resume_cursor)
    if state.resume_cursor is not None and task is None:
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.ESCALATE,
            task_id=state.resume_cursor,
            reason="resume cursor points to an unknown task",
            safe_to_continue=False,
        )

    if status in {"pending", "in_progress", "running", "cycle_limit"}:
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.RESUME,
            task_id=state.resume_cursor,
            reason="durable goal has unfinished work that can be resumed",
            attempts=0 if task is None else task.attempts,
            safe_to_continue=state.resume_cursor is not None,
        )

    if status == "replan_required":
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.REPLAN,
            task_id=state.resume_cursor,
            reason="supervisor explicitly requested a new plan",
            attempts=0 if task is None else task.attempts,
            safe_to_continue=False,
        )

    if status == "blocked":
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.ESCALATE,
            task_id=state.resume_cursor,
            reason="goal is blocked with no READY task",
            attempts=0 if task is None else task.attempts,
            safe_to_continue=False,
        )

    if task is not None and task.status in {"failed", "retry", "repair", "ready"}:
        if task.attempts < config.max_retry_attempts:
            return RecoveryDecision(
                goal_id=state.goal_id,
                action=RecoveryAction.RETRY,
                task_id=task.task_id,
                reason="failed task is still inside the retry budget",
                attempts=task.attempts,
                safe_to_continue=True,
            )
        if task.attempts < config.max_repair_attempts:
            return RecoveryDecision(
                goal_id=state.goal_id,
                action=RecoveryAction.REPAIR,
                task_id=task.task_id,
                reason="retry budget exhausted; task is eligible for repair",
                attempts=task.attempts,
                safe_to_continue=True,
            )
        return RecoveryDecision(
            goal_id=state.goal_id,
            action=RecoveryAction.REPLAN,
            task_id=task.task_id,
            reason="retry and repair budgets are exhausted",
            attempts=task.attempts,
            safe_to_continue=False,
        )

    return RecoveryDecision(
        goal_id=state.goal_id,
        action=RecoveryAction.ESCALATE,
        task_id=state.resume_cursor,
        reason=f"unsupported durable recovery state: {state.status}",
        attempts=0 if task is None else task.attempts,
        safe_to_continue=False,
    )
