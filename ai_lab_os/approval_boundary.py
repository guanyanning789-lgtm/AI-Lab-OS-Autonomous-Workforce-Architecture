from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore, PersistentTaskState
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus, TaskExecutor
from ai_lab_os.task_planner import PlannedTask


class ApprovalRisk(str, Enum):
    SAFE = "safe"
    REAL_COMPUTER_ACTION = "real_computer_action"


@dataclass(frozen=True)
class ApprovalRequest:
    goal_id: str
    task_id: str
    action: str
    reason: str
    risk: ApprovalRisk


@dataclass(frozen=True)
class ApprovalResult:
    goal_id: str
    task_id: str
    approved: bool
    event: str


class ApprovalService:
    """Explicit, process-local grants plus durable goal-state transitions.

    Grants intentionally do not survive a process restart. A restarted service
    must ask again before a sensitive real action, which is the fail-closed choice.
    The durable goal remains in approval_required until approve() is called.
    """

    def __init__(self, goal_store: JsonGoalStore) -> None:
        self._goal_store = goal_store
        self._grants: set[tuple[str, str]] = set()

    def is_approved(self, goal_id: str, task_id: str) -> bool:
        return (goal_id, task_id) in self._grants

    def approve(self, goal_id: str, task_id: str) -> ApprovalResult:
        state = self._goal_store.load(goal_id)
        if state.status != "approval_required":
            raise ValueError(f"goal is not waiting for approval: {state.status}")
        if state.resume_cursor != task_id:
            raise ValueError("task_id does not match the goal resume cursor")

        updated_tasks: list[PersistentTaskState] = []
        found = False
        for task in state.tasks:
            if task.task_id != task_id:
                updated_tasks.append(task)
                continue
            found = True
            if task.status != "awaiting_approval":
                raise ValueError(f"task is not awaiting approval: {task.status}")
            updated_tasks.append(replace(task, status="ready", message=""))
        if not found:
            raise LookupError(f"unknown task_id: {task_id}")

        self._grants.add((goal_id, task_id))
        event = f"APPROVED:{task_id}"
        self._goal_store.save(replace(
            state,
            status="in_progress",
            tasks=tuple(updated_tasks),
            events=state.events + (event,),
        ))
        return ApprovalResult(goal_id, task_id, True, event)

    def reject(self, goal_id: str, task_id: str) -> ApprovalResult:
        state = self._goal_store.load(goal_id)
        if state.status != "approval_required" or state.resume_cursor != task_id:
            raise ValueError("goal/task is not waiting for this approval")
        event = f"APPROVAL_REJECTED:{task_id}"
        self._goal_store.save(replace(
            state,
            status="paused",
            events=state.events + (event,),
        ))
        self._grants.discard((goal_id, task_id))
        return ApprovalResult(goal_id, task_id, False, event)


@dataclass
class ApprovalAwareExecutor:
    """Gate sensitive real Computer work before it reaches the real executor."""

    inner: TaskExecutor
    approvals: ApprovalService
    real_computer_actions_enabled: bool = False

    def __call__(self, task: PlannedTask) -> TaskExecutionResult:
        if task.agent is not AgentKind.COMPUTER:
            return self.inner(task)

        # V1.0 defaults fail closed. Existing dry-run computer executors continue
        # to work without approval because real actions are not enabled here.
        if not self.real_computer_actions_enabled:
            return self.inner(task)

        action = task.metadata.get("action", "computer_action").strip() or "computer_action"
        if not self.approvals.is_approved(task.goal_id, task.task_id):
            return TaskExecutionResult(
                TaskExecutionStatus.AWAITING_APPROVAL,
                f"approval required before real computer action: {action}",
            )
        return self.inner(task)
