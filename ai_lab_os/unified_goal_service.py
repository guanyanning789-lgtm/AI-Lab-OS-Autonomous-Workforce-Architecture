from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.goal_contract import GoalPriority
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
    priority: GoalPriority = GoalPriority.NORMAL
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        goal = self.goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")
        if self.goal_id is not None and not self.goal_id.strip():
            raise ValueError("goal_id must not be blank when provided")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata.items()):
            raise ValueError("metadata keys and values must be strings")
        object.__setattr__(self, "goal", goal)


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
    """Stable product-facing entry point for one natural-language goal.

    The service owns request normalization and response shaping only. Execution,
    persistence, recovery, and safety remain delegated to the already-proven V0.8
    orchestration path.
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
            request=request.goal,
            goal_id=request.goal_id,
            success_criteria=request.success_criteria,
            constraints=request.constraints,
            priority=request.priority,
            metadata=dict(request.metadata),
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
        return self._shape_result(result)

    def _shape_result(self, result: RecoveryHandoffResult) -> GoalSubmissionResult:
        saved = self._goal_store.load(result.goal_id)
        selected_skill = result.launch.routed.routed.selection.skill
        message = result.launch.supervisor.message
        if result.recovery is not None:
            recovery_result = next(
                (item for item in result.recovery.results if item.goal_id == result.goal_id),
                None,
            )
            if recovery_result is not None and recovery_result.supervisor_result is not None:
                message = recovery_result.supervisor_result.message
        return GoalSubmissionResult(
            goal_id=result.goal_id,
            skill_id=selected_skill.skill_id,
            status=result.final_status,
            handed_off=result.handed_off,
            resume_cursor=saved.resume_cursor,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            message=message,
        )
