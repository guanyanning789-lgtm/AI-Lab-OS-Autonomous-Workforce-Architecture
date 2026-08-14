from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ai_lab_os.execution_history import JsonExecutionHistory
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_policy import RecoveryAction, RecoveryPolicyConfig
from ai_lab_os.recovery_runner import RecoveryRunResult, ReplanHandler, recover_all
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutor


@dataclass(frozen=True)
class RecoveryDaemonConfig:
    poll_seconds: float = 30.0
    max_scans: int | None = None
    stop_when_idle: bool = False

    def __post_init__(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")
        if self.max_scans is not None and self.max_scans < 1:
            raise ValueError("max_scans must be >= 1 when provided")


@dataclass(frozen=True)
class RecoveryScanReport:
    scan_number: int
    total_goals: int
    actionable_goals: int
    completed_goals: int
    escalated_goals: int
    replan_goals: int
    results: tuple[RecoveryRunResult, ...]

    @property
    def idle(self) -> bool:
        return self.actionable_goals == 0


SleepFn = Callable[[float], None]
ReportFn = Callable[[RecoveryScanReport], None]


def scan_once(
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    scan_number: int = 1,
    recovery_config: RecoveryPolicyConfig | None = None,
    supervisor_policy: SupervisorPolicy | None = None,
    history_store: JsonExecutionHistory | None = None,
    replan_handler: ReplanHandler | None = None,
) -> RecoveryScanReport:
    results = recover_all(
        executor,
        goal_store,
        recovery_config=recovery_config,
        supervisor_policy=supervisor_policy,
        history_store=history_store,
        replan_handler=replan_handler,
    )

    actionable = 0
    completed = 0
    escalated = 0
    replan = 0
    for result in results:
        action = result.decision.action
        if action is RecoveryAction.NONE:
            completed += 1
            continue
        if result.status == "escalated":
            escalated += 1
            continue
        if result.status == "replan_required":
            replan += 1
            continue
        actionable += 1

    return RecoveryScanReport(
        scan_number=scan_number,
        total_goals=len(results),
        actionable_goals=actionable,
        completed_goals=completed,
        escalated_goals=escalated,
        replan_goals=replan,
        results=results,
    )


def run_recovery_daemon(
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    config: RecoveryDaemonConfig | None = None,
    recovery_config: RecoveryPolicyConfig | None = None,
    supervisor_policy: SupervisorPolicy | None = None,
    history_store: JsonExecutionHistory | None = None,
    replan_handler: ReplanHandler | None = None,
    sleep_fn: SleepFn = time.sleep,
    report_fn: ReportFn | None = None,
) -> tuple[RecoveryScanReport, ...]:
    """Continuously scan durable goals and trigger bounded recovery actions.

    The daemon is deliberately simple and deterministic: one full scan finishes
    before the next begins, preventing overlapping recovery of the same goal.
    Escalated or unresolved replan goals are reported but not retried in a tight
    loop inside the same scan.
    """

    config = config or RecoveryDaemonConfig()
    reports: list[RecoveryScanReport] = []
    scan_number = 0

    while True:
        scan_number += 1
        report = scan_once(
            executor,
            goal_store,
            scan_number=scan_number,
            recovery_config=recovery_config,
            supervisor_policy=supervisor_policy,
            history_store=history_store,
            replan_handler=replan_handler,
        )
        reports.append(report)
        if report_fn is not None:
            report_fn(report)

        if config.stop_when_idle and report.idle:
            break
        if config.max_scans is not None and scan_number >= config.max_scans:
            break
        sleep_fn(config.poll_seconds)

    return tuple(reports)
