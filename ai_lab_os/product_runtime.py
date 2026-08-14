from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.goal_lifecycle_service import GoalLifecycleResult, GoalLifecycleService
from ai_lab_os.goal_query_service import GoalQueryService, GoalStatusSnapshot
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_daemon import RecoveryScanReport, scan_once
from ai_lab_os.recovery_policy import RecoveryPolicyConfig
from ai_lab_os.recovery_runner import ReplanHandler
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutor
from ai_lab_os.unified_goal_service import GoalSubmissionRequest, GoalSubmissionResult, UnifiedGoalService


@dataclass(frozen=True)
class ProductRuntimeConfig:
    poll_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")


@dataclass(frozen=True)
class ProductRuntimeTick:
    tick_number: int
    recovery: RecoveryScanReport

    @property
    def idle(self) -> bool:
        return self.recovery.actionable_goals == 0


SleepFn = Callable[[float], None]
TickFn = Callable[[ProductRuntimeTick], None]


class ProductRuntime:
    """Always-on product core above the proven durable orchestration stack."""

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
        config: ProductRuntimeConfig | None = None,
    ) -> None:
        self._executor = executor
        self._goal_store = goal_store
        self._history_store = history_store
        self._recovery_policy = recovery_policy
        self._recovery_config = recovery_config
        self._replan_handler = replan_handler
        self.config = config or ProductRuntimeConfig()
        self.goals = UnifiedGoalService(
            registry,
            executor,
            goal_store,
            history_store=history_store,
            launch_policy=launch_policy,
            recovery_policy=recovery_policy,
            recovery_config=recovery_config,
            replan_handler=replan_handler,
            min_score=min_score,
        )
        self.query = GoalQueryService(goal_store)
        self.lifecycle = GoalLifecycleService(goal_store)
        self._tick_number = 0

    def submit(self, request: GoalSubmissionRequest) -> GoalSubmissionResult:
        return self.goals.submit_goal(request)

    def get_goal(self, goal_id: str) -> GoalStatusSnapshot:
        return self.query.get_goal(goal_id)

    def list_goals(self, *, status: str | None = None) -> tuple[GoalStatusSnapshot, ...]:
        return self.query.list_goals(status=status)

    def get_events(self, goal_id: str, *, after: int = 0) -> tuple[str, ...]:
        return self.query.get_events(goal_id, after=after)

    def pause(self, goal_id: str) -> GoalLifecycleResult:
        return self.lifecycle.pause(goal_id)

    def cancel(self, goal_id: str) -> GoalLifecycleResult:
        return self.lifecycle.cancel(goal_id)

    def resume(self, goal_id: str) -> GoalLifecycleResult:
        return self.lifecycle.resume(goal_id)

    def tick(self) -> ProductRuntimeTick:
        self._tick_number += 1
        report = scan_once(
            self._executor,
            self._goal_store,
            scan_number=self._tick_number,
            recovery_config=self._recovery_config,
            supervisor_policy=self._recovery_policy,
            history_store=self._history_store,
            replan_handler=self._replan_handler,
        )
        return ProductRuntimeTick(tick_number=self._tick_number, recovery=report)

    def run(
        self,
        *,
        max_ticks: int | None = None,
        stop_when_idle: bool = False,
        sleep_fn: SleepFn = time.sleep,
        tick_fn: TickFn | None = None,
    ) -> tuple[ProductRuntimeTick, ...]:
        if max_ticks is not None and max_ticks < 1:
            raise ValueError("max_ticks must be >= 1 when provided")

        ticks: list[ProductRuntimeTick] = []
        while True:
            current = self.tick()
            ticks.append(current)
            if tick_fn is not None:
                tick_fn(current)
            if stop_when_idle and current.idle:
                break
            if max_ticks is not None and len(ticks) >= max_ticks:
                break
            sleep_fn(self.config.poll_seconds)
        return tuple(ticks)
