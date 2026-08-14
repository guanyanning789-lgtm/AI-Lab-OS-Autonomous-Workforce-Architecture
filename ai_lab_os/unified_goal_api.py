from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_handoff import RecoveryHandoffResult, launch_with_recovery_handoff
from ai_lab_os.recovery_policy import RecoveryPolicyConfig
from ai_lab_os.recovery_runner import ReplanHandler
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutor


@dataclass(frozen=True)
class GoalSubmissionRequest:
    goal: str
    goal_id: str | None = None
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    priority: int = 50

    def __post_init__(self) -> None:
        if not self.goal.strip():
            raise ValueError("goal must not be empty")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")


@dataclass(frozen=True)
class GoalSubmissionResult:
    goal_id: str
    skill_id: str
    status: str
    handed_off: bool
    resume_cursor: str | None
    submitted_at: str
    message: str


class UnifiedGoalService:
    """Stable product-facing boundary for one-request autonomous orchestration.

    This service is deliberately transport-agnostic. HTTP/CLI/UI adapters can call
    the same submit_goal method without owning Skill routing, persistence,
    Supervisor execution, or recovery semantics.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        executor: TaskExecutor,
        goal_store: JsonGoalStore,
        *,
        history_store: JsonExecutionHistory | None = None,
        launch_policy: SupervisorPolicy | None = None,
        recovery_policy: SupervisorPolicy | None = None,
        recovery_config: RecoveryPolicyConfig | None = None,
        replan_handler: ReplanHandler | None = None,
        min_score: int = 2,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._goal_store = goal_store
        self._history_store = history_store
        self._launch_policy = launch_policy
        self._recovery_policy = recovery_policy
        self._recovery_config = recovery_config
        self._replan_handler = replan_handler
        self._min_score = min_score

    def submit_goal(self, request: GoalSubmissionRequest) -> GoalSubmissionResult:
        intake = GoalIntakeRequest(
            request.goal,
            goal_id=request.goal_id,
            success_criteria=request.success_criteria,
            constraints=request.constraints,
            priority=request.priority,
        )
        result = launch_with_recovery_handoff(
            intake,
            self._registry,
            self._executor,
            self._goal_store,
            launch_policy=self._launch_policy,
            recovery_policy=self._recovery_policy,
            recovery_config=self._recovery_config,
            history_store=self._history_store,
            replan_handler=self._replan_handler,
            min_score=self._min_score,
        )
        return self._to_submission_result(result)

    def _to_submission_result(self, result: RecoveryHandoffResult) -> GoalSubmissionResult:
        persisted = self._goal_store.load(result.goal_id)
        skill_id = result.launch.routed.routed.selection.skill.skill_id
        status = result.final_status
        if status == "complete":
            message = "Goal completed successfully."
        elif result.handed_off:
            message = f"Goal handed to recovery with status: {status}."
        else:
            message = f"Goal launch ended with status: {status}."
        return GoalSubmissionResult(
            goal_id=result.goal_id,
            skill_id=skill_id,
            status=status,
            handed_off=result.handed_off,
            resume_cursor=persisted.resume_cursor,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            message=message,
        )
