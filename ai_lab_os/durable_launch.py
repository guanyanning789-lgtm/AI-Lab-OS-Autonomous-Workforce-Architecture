from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.intake_router import IntakeRoutingResult, intake_and_route
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, SupervisorRunResult, TaskExecutor, run_supervisor_loop


@dataclass(frozen=True)
class DurableLaunchResult:
    routed: IntakeRoutingResult
    supervisor: SupervisorRunResult

    @property
    def goal_id(self) -> str:
        return self.routed.intake.contract.goal_id


def launch_goal(
    request: GoalIntakeRequest,
    registry: SkillRegistry,
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    supervisor_policy: SupervisorPolicy | None = None,
    history_store: JsonExecutionHistory | None = None,
    min_score: int = 2,
) -> DurableLaunchResult:
    """Route one natural-language goal and launch it through durable Supervisor execution."""

    routed = intake_and_route(request, registry, min_score=min_score)
    plan = routed.routed.compiled.plan

    # Fail closed on accidental goal-id reuse. A durable goal must be resumed
    # through RecoveryRunner rather than silently overwritten by a new launch.
    existing_ids = {state.goal_id for state in goal_store.list()}
    if plan.goal_id in existing_ids:
        raise ValueError(f"durable goal already exists: {plan.goal_id}")

    supervisor = run_supervisor_loop(
        plan,
        executor,
        policy=supervisor_policy,
        goal_store=goal_store,
        history_store=history_store,
    )
    return DurableLaunchResult(routed=routed, supervisor=supervisor)
