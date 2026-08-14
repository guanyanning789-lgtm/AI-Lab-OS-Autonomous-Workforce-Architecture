from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ai_lab_os.task_planner import TaskPlanContract


class TaskLifecycleStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"
    RETRY = "retry"
    REPAIR = "repair"
    REPLAN = "replan"


_ALLOWED_TRANSITIONS: dict[TaskLifecycleStatus, set[TaskLifecycleStatus]] = {
    TaskLifecycleStatus.PENDING: {TaskLifecycleStatus.READY},
    TaskLifecycleStatus.READY: {TaskLifecycleStatus.RUNNING},
    TaskLifecycleStatus.RUNNING: {
        TaskLifecycleStatus.VERIFYING,
        TaskLifecycleStatus.FAILED,
    },
    TaskLifecycleStatus.VERIFYING: {
        TaskLifecycleStatus.COMPLETE,
        TaskLifecycleStatus.FAILED,
    },
    TaskLifecycleStatus.FAILED: {
        TaskLifecycleStatus.RETRY,
        TaskLifecycleStatus.REPAIR,
        TaskLifecycleStatus.REPLAN,
    },
    TaskLifecycleStatus.RETRY: {TaskLifecycleStatus.READY},
    TaskLifecycleStatus.REPAIR: {TaskLifecycleStatus.READY},
    TaskLifecycleStatus.REPLAN: set(),
    TaskLifecycleStatus.COMPLETE: set(),
}


@dataclass
class TaskRuntimeState:
    task_id: str
    status: TaskLifecycleStatus = TaskLifecycleStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    history: list[TaskLifecycleStatus] = field(default_factory=lambda: [TaskLifecycleStatus.PENDING])

    def transition(self, target: TaskLifecycleStatus, *, error: str | None = None) -> None:
        allowed = _ALLOWED_TRANSITIONS[self.status]
        if target not in allowed:
            raise ValueError(f"invalid task transition: {self.status.value} -> {target.value}")

        if target is TaskLifecycleStatus.RUNNING:
            self.attempts += 1
        if target is TaskLifecycleStatus.FAILED:
            self.last_error = (error or "task failed").strip()
        elif target in {TaskLifecycleStatus.COMPLETE, TaskLifecycleStatus.READY}:
            self.last_error = None

        self.status = target
        self.history.append(target)


@dataclass
class PlanRuntimeState:
    plan: TaskPlanContract
    tasks: dict[str, TaskRuntimeState]

    @classmethod
    def from_plan(cls, plan: TaskPlanContract) -> "PlanRuntimeState":
        runtime = cls(
            plan=plan,
            tasks={task.task_id: TaskRuntimeState(task_id=task.task_id) for task in plan.tasks},
        )
        runtime.refresh_ready_tasks()
        return runtime

    def refresh_ready_tasks(self) -> tuple[str, ...]:
        newly_ready: list[str] = []
        for task in self.plan.tasks:
            state = self.tasks[task.task_id]
            if state.status is not TaskLifecycleStatus.PENDING:
                continue
            if all(self.tasks[dependency].status is TaskLifecycleStatus.COMPLETE for dependency in task.depends_on):
                state.transition(TaskLifecycleStatus.READY)
                newly_ready.append(task.task_id)
        return tuple(newly_ready)

    def next_ready_task_id(self) -> str | None:
        self.refresh_ready_tasks()
        for task in self.plan.tasks:
            if self.tasks[task.task_id].status is TaskLifecycleStatus.READY:
                return task.task_id
        return None

    def mark_complete(self, task_id: str) -> None:
        state = self._state(task_id)
        if state.status is TaskLifecycleStatus.RUNNING:
            state.transition(TaskLifecycleStatus.VERIFYING)
        if state.status is not TaskLifecycleStatus.VERIFYING:
            raise ValueError("task must be running or verifying before completion")
        state.transition(TaskLifecycleStatus.COMPLETE)
        self.refresh_ready_tasks()

    def mark_failed(self, task_id: str, error: str) -> None:
        state = self._state(task_id)
        if state.status not in {TaskLifecycleStatus.RUNNING, TaskLifecycleStatus.VERIFYING}:
            raise ValueError("task must be running or verifying before failure")
        state.transition(TaskLifecycleStatus.FAILED, error=error)

    def request_recovery(self, task_id: str, strategy: TaskLifecycleStatus) -> None:
        if strategy not in {
            TaskLifecycleStatus.RETRY,
            TaskLifecycleStatus.REPAIR,
            TaskLifecycleStatus.REPLAN,
        }:
            raise ValueError("recovery strategy must be retry, repair, or replan")
        state = self._state(task_id)
        state.transition(strategy)
        if strategy in {TaskLifecycleStatus.RETRY, TaskLifecycleStatus.REPAIR}:
            state.transition(TaskLifecycleStatus.READY)

    def all_complete(self) -> bool:
        return all(state.status is TaskLifecycleStatus.COMPLETE for state in self.tasks.values())

    def _state(self, task_id: str) -> TaskRuntimeState:
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task_id: {task_id}") from exc
