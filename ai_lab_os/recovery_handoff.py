from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.durable_launch import DurableLaunchResult, launch_goal
from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_daemon import RecoveryScanReport, scan_once
from ai_lab_os.recovery_policy import RecoveryPolicyConfig
from ai_lab_os.recovery_runner import ReplanHandler
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutor


@dataclass(frozen=True)
class RecoveryHandoffResult:
    launch: DurableLaunchResult
    recovery: RecoveryScanReport | None

    @property
    def goal_id(self) -> str:
        return self.launch.goal_id

    @property
    def final_status(self) -> str:
        if self.recovery is None:
            return self.launch.supervisor.status
        for result in self.recovery.results:
            if result.goal_id == self.goal_id:
                return result.status
        return self.launch.supervisor.status

    @property
    def handed_off(self) -> bool:
        return self.recovery is not None


def launch_with_recovery_handoff(
    request: GoalIntakeRequest,
    registry: SkillRegistry,
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    launch_policy: SupervisorPolicy | None = None,
    recovery_policy: SupervisorPolicy | None = None,
    recovery_config: RecoveryPolicyConfig | None = None,
    history_store: JsonExecutionHistory | None = None,
    replan_handler: ReplanHandler | None = None,
    min_score: int = 2,
) -> RecoveryHandoffResult:
    """Launch one natural-language goal and automatically hand unfinished work to recovery.

    A completed launch is returned immediately. Any durable non-complete result is
    left in JsonGoalStore by Supervisor and then consumed through the same bounded
    recovery path used by RecoveryDaemon. This removes the manual launch->resume
    plumbing without weakening recovery policy or persistence semantics.
    """

    launched = launch_goal(
        request,
        registry,
        executor,
        goal_store,
        supervisor_policy=launch_policy,
        history_store=history_store,
        min_score=min_score,
    )
    if launched.supervisor.status == "complete":
        return RecoveryHandoffResult(launch=launched, recovery=None)

    report = scan_once(
        executor,
        goal_store,
        recovery_config=recovery_config,
        supervisor_policy=recovery_policy,
        history_store=history_store,
        replan_handler=replan_handler,
    )
    return RecoveryHandoffResult(launch=launched, recovery=report)
