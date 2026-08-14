from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState
from ai_lab_os.recovery_policy import RecoveryAction, RecoveryDecision, RecoveryPolicyConfig, decide_recovery
from ai_lab_os.supervisor_loop import SupervisorPolicy, SupervisorRunResult, TaskExecutor, resume_supervisor_from_store


@dataclass(frozen=True)
class RecoveryRunResult:
    goal_id: str
    decision: RecoveryDecision
    status: str
    supervisor_result: SupervisorRunResult | None = None


ReplanHandler = Callable[[PersistentGoalState, RecoveryDecision], RecoveryRunResult]


def recover_goal(
    goal_id: str,
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    recovery_config: RecoveryPolicyConfig | None = None,
    supervisor_policy: SupervisorPolicy | None = None,
    history_store: JsonExecutionHistory | None = None,
    replan_handler: ReplanHandler | None = None,
) -> RecoveryRunResult:
    state = goal_store.load(goal_id)
    decision = decide_recovery(state, config=recovery_config)

    if decision.action is RecoveryAction.NONE:
        return RecoveryRunResult(goal_id, decision, "no_action")

    if decision.action in {RecoveryAction.RESUME, RecoveryAction.RETRY, RecoveryAction.REPAIR}:
        if not decision.safe_to_continue:
            return RecoveryRunResult(goal_id, decision, "escalated")
        supervisor_result = resume_supervisor_from_store(
            goal_id,
            executor,
            goal_store,
            policy=supervisor_policy,
            history_store=history_store,
        )
        return RecoveryRunResult(
            goal_id=goal_id,
            decision=decision,
            status=supervisor_result.status,
            supervisor_result=supervisor_result,
        )

    if decision.action is RecoveryAction.REPLAN:
        if replan_handler is None:
            return RecoveryRunResult(goal_id, decision, "replan_required")
        return replan_handler(state, decision)

    return RecoveryRunResult(goal_id, decision, "escalated")


def recover_all(
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    recovery_config: RecoveryPolicyConfig | None = None,
    supervisor_policy: SupervisorPolicy | None = None,
    history_store: JsonExecutionHistory | None = None,
    replan_handler: ReplanHandler | None = None,
) -> tuple[RecoveryRunResult, ...]:
    results: list[RecoveryRunResult] = []
    for state in goal_store.list():
        results.append(
            recover_goal(
                state.goal_id,
                executor,
                goal_store,
                recovery_config=recovery_config,
                supervisor_policy=supervisor_policy,
                history_store=history_store,
                replan_handler=replan_handler,
            )
        )
    return tuple(results)
