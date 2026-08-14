from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ai_lab_os.task_planner import PlannedTask, TaskPlanContract
from ai_lab_os.task_state import PlanRuntimeState, TaskLifecycleStatus


class TaskExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_REPLAN = "needs_replan"


@dataclass(frozen=True)
class TaskExecutionResult:
    status: TaskExecutionStatus
    message: str = ""


@dataclass(frozen=True)
class SupervisorPolicy:
    max_attempts_per_task: int = 2
    max_cycles: int = 50

    def __post_init__(self) -> None:
        if self.max_attempts_per_task < 1:
            raise ValueError("max_attempts_per_task must be >= 1")
        if self.max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")


@dataclass
class SupervisorRunResult:
    goal_id: str
    status: str
    cycles: int
    completed_tasks: tuple[str, ...]
    failed_task_id: str | None = None
    message: str = ""
    events: list[str] = field(default_factory=list)


TaskExecutor = Callable[[PlannedTask], TaskExecutionResult]


def _planned_task(plan: TaskPlanContract, task_id: str) -> PlannedTask:
    for task in plan.tasks:
        if task.task_id == task_id:
            return task
    raise KeyError(f"unknown task_id: {task_id}")


def run_supervisor_loop(
    plan: TaskPlanContract,
    executor: TaskExecutor,
    *,
    policy: SupervisorPolicy | None = None,
) -> SupervisorRunResult:
    """Drive one task plan until the goal completes or requires replanning.

    V0.3.4 intentionally keeps task execution behind a callback. Agent routing and
    real worker dispatch are added in the next milestone, while this loop owns the
    orchestration semantics: select READY work, run it, update state, recover, and
    stop only when the goal is complete or cannot safely continue.
    """

    policy = policy or SupervisorPolicy()
    runtime = PlanRuntimeState.from_plan(plan)
    events: list[str] = []
    cycles = 0

    while cycles < policy.max_cycles:
        if runtime.all_complete():
            completed = tuple(task.task_id for task in plan.tasks)
            events.append("GOAL_COMPLETE")
            return SupervisorRunResult(
                goal_id=plan.goal_id,
                status="complete",
                cycles=cycles,
                completed_tasks=completed,
                message="All planned tasks completed successfully.",
                events=events,
            )

        task_id = runtime.next_ready_task_id()
        if task_id is None:
            replan_task = next(
                (
                    task.task_id
                    for task in plan.tasks
                    if runtime.tasks[task.task_id].status is TaskLifecycleStatus.REPLAN
                ),
                None,
            )
            if replan_task is not None:
                events.append(f"REPLAN_REQUIRED:{replan_task}")
                return SupervisorRunResult(
                    goal_id=plan.goal_id,
                    status="replan_required",
                    cycles=cycles,
                    completed_tasks=tuple(
                        task.task_id
                        for task in plan.tasks
                        if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE
                    ),
                    failed_task_id=replan_task,
                    message="Supervisor requires a new plan before continuing.",
                    events=events,
                )

            return SupervisorRunResult(
                goal_id=plan.goal_id,
                status="blocked",
                cycles=cycles,
                completed_tasks=tuple(
                    task.task_id
                    for task in plan.tasks
                    if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE
                ),
                message="No READY task is available and the plan is not complete.",
                events=events,
            )

        cycles += 1
        state = runtime.tasks[task_id]
        state.transition(TaskLifecycleStatus.RUNNING)
        events.append(f"RUNNING:{task_id}:attempt={state.attempts}")

        task = _planned_task(plan, task_id)
        try:
            result = executor(task)
        except Exception as exc:
            result = TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message=f"executor exception: {exc}",
            )

        if result.status is TaskExecutionStatus.SUCCESS:
            runtime.mark_complete(task_id)
            events.append(f"COMPLETE:{task_id}")
            continue

        error = result.message.strip() or "task execution failed"
        runtime.mark_failed(task_id, error)
        events.append(f"FAILED:{task_id}:{error}")

        if result.status is TaskExecutionStatus.NEEDS_REPLAN:
            runtime.request_recovery(task_id, TaskLifecycleStatus.REPLAN)
            events.append(f"REPLAN:{task_id}")
            continue

        if state.attempts < policy.max_attempts_per_task:
            strategy = (
                TaskLifecycleStatus.RETRY
                if state.attempts == 1
                else TaskLifecycleStatus.REPAIR
            )
            runtime.request_recovery(task_id, strategy)
            events.append(f"{strategy.value.upper()}:{task_id}")
            continue

        runtime.request_recovery(task_id, TaskLifecycleStatus.REPLAN)
        events.append(f"REPLAN:{task_id}")

    return SupervisorRunResult(
        goal_id=plan.goal_id,
        status="cycle_limit",
        cycles=cycles,
        completed_tasks=tuple(
            task.task_id
            for task in plan.tasks
            if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE
        ),
        message="Supervisor stopped after reaching max_cycles.",
        events=events,
    )
