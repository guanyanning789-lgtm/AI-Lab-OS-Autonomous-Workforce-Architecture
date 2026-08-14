from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentGoalState, PersistentTaskState
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


def _persist_runtime(
    store: JsonGoalStore | None,
    plan: TaskPlanContract,
    runtime: PlanRuntimeState,
    *,
    cycles: int,
    events: list[str],
    goal_status: str | None = None,
) -> None:
    if store is None:
        return

    try:
        previous = store.load(plan.goal_id)
        created_at = previous.created_at
        schema_version = previous.schema_version
    except LookupError:
        previous = None
        initial = PersistentGoalState.from_plan(plan)
        created_at = initial.created_at
        schema_version = "0.6.2"

    task_states = tuple(
        PersistentTaskState(
            task_id=task.task_id,
            status=runtime.tasks[task.task_id].status.value,
            attempts=runtime.tasks[task.task_id].attempts,
            message=runtime.tasks[task.task_id].last_error or "",
            evidence=(
                previous_task.evidence
                if previous is not None
                and (previous_task := next(
                    (item for item in previous.tasks if item.task_id == task.task_id),
                    None,
                )) is not None
                else ()
            ),
        )
        for task in plan.tasks
    )

    resume_cursor = next(
        (
            task.task_id
            for task in plan.tasks
            if runtime.tasks[task.task_id].status is not TaskLifecycleStatus.COMPLETE
        ),
        None,
    )
    if goal_status is None:
        if runtime.all_complete():
            goal_status = "complete"
        elif any(state.status is TaskLifecycleStatus.REPLAN for state in runtime.tasks.values()):
            goal_status = "replan_required"
        elif any(state.status is TaskLifecycleStatus.RUNNING for state in runtime.tasks.values()):
            goal_status = "running"
        else:
            goal_status = "in_progress"

    store.save(
        PersistentGoalState(
            goal_id=plan.goal_id,
            status=goal_status,
            plan=plan.to_dict(),
            tasks=task_states,
            resume_cursor=resume_cursor,
            cycles=cycles,
            events=tuple(events),
            created_at=created_at,
            schema_version=schema_version,
        )
    )


def run_supervisor_loop(
    plan: TaskPlanContract,
    executor: TaskExecutor,
    *,
    policy: SupervisorPolicy | None = None,
    goal_store: JsonGoalStore | None = None,
    resume_state: PersistentGoalState | None = None,
) -> SupervisorRunResult:
    """Drive or resume one task plan while optionally persisting every transition."""

    policy = policy or SupervisorPolicy()
    if resume_state is not None:
        runtime = PlanRuntimeState.from_persistent_goal(plan, resume_state)
        events = list(resume_state.events)
        cycles = resume_state.cycles
        events.append(f"RESUME:{resume_state.resume_cursor or 'complete'}")
    else:
        runtime = PlanRuntimeState.from_plan(plan)
        events: list[str] = []
        cycles = 0
    _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)

    while cycles < policy.max_cycles:
        if runtime.all_complete():
            completed = tuple(task.task_id for task in plan.tasks)
            events.append("GOAL_COMPLETE")
            _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events, goal_status="complete")
            return SupervisorRunResult(plan.goal_id, "complete", cycles, completed, message="All planned tasks completed successfully.", events=events)

        task_id = runtime.next_ready_task_id()
        if task_id is None:
            replan_task = next((task.task_id for task in plan.tasks if runtime.tasks[task.task_id].status is TaskLifecycleStatus.REPLAN), None)
            if replan_task is not None:
                events.append(f"REPLAN_REQUIRED:{replan_task}")
                _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events, goal_status="replan_required")
                return SupervisorRunResult(
                    goal_id=plan.goal_id,
                    status="replan_required",
                    cycles=cycles,
                    completed_tasks=tuple(task.task_id for task in plan.tasks if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE),
                    failed_task_id=replan_task,
                    message="Supervisor requires a new plan before continuing.",
                    events=events,
                )
            _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events, goal_status="blocked")
            return SupervisorRunResult(
                goal_id=plan.goal_id,
                status="blocked",
                cycles=cycles,
                completed_tasks=tuple(task.task_id for task in plan.tasks if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE),
                message="No READY task is available and the plan is not complete.",
                events=events,
            )

        cycles += 1
        state = runtime.tasks[task_id]
        state.transition(TaskLifecycleStatus.RUNNING)
        events.append(f"RUNNING:{task_id}:attempt={state.attempts}")
        _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)

        task = _planned_task(plan, task_id)
        try:
            result = executor(task)
        except Exception as exc:
            result = TaskExecutionResult(TaskExecutionStatus.FAILED, f"executor exception: {exc}")

        if result.status is TaskExecutionStatus.SUCCESS:
            runtime.mark_complete(task_id)
            events.append(f"COMPLETE:{task_id}")
            _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)
            continue

        error = result.message.strip() or "task execution failed"
        runtime.mark_failed(task_id, error)
        events.append(f"FAILED:{task_id}:{error}")
        _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)

        if result.status is TaskExecutionStatus.NEEDS_REPLAN:
            runtime.request_recovery(task_id, TaskLifecycleStatus.REPLAN)
            events.append(f"REPLAN:{task_id}")
            _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)
            continue

        if state.attempts < policy.max_attempts_per_task:
            strategy = TaskLifecycleStatus.RETRY if state.attempts == 1 else TaskLifecycleStatus.REPAIR
            runtime.request_recovery(task_id, strategy)
            events.append(f"{strategy.value.upper()}:{task_id}")
            _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)
            continue

        runtime.request_recovery(task_id, TaskLifecycleStatus.REPLAN)
        events.append(f"REPLAN:{task_id}")
        _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events)

    _persist_runtime(goal_store, plan, runtime, cycles=cycles, events=events, goal_status="cycle_limit")
    return SupervisorRunResult(
        goal_id=plan.goal_id,
        status="cycle_limit",
        cycles=cycles,
        completed_tasks=tuple(task.task_id for task in plan.tasks if runtime.tasks[task.task_id].status is TaskLifecycleStatus.COMPLETE),
        message="Supervisor stopped after reaching max_cycles.",
        events=events,
    )


def resume_supervisor_from_store(
    goal_id: str,
    executor: TaskExecutor,
    goal_store: JsonGoalStore,
    *,
    policy: SupervisorPolicy | None = None,
) -> SupervisorRunResult:
    """Reload a persisted goal after process restart and continue unfinished work."""

    persisted = goal_store.load(goal_id)
    plan = TaskPlanContract.from_dict(persisted.plan)
    return run_supervisor_loop(plan, executor, policy=policy, goal_store=goal_store, resume_state=persisted)
