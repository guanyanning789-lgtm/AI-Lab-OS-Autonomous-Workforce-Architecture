from __future__ import annotations

from dataclasses import dataclass, field

from ai_lab_os.models import AgentKind, TaskPlan, TaskStatus


@dataclass
class TaskState:
    plan: TaskPlan
    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0
    completed_steps: list[int] = field(default_factory=list)
    failed_steps: list[int] = field(default_factory=list)
    retry_counts: dict[int, int] = field(default_factory=dict)

    def start(self) -> None:
        if self.status not in {TaskStatus.PENDING, TaskStatus.BLOCKED}:
            raise ValueError(f"cannot start task from {self.status.value}")
        self.status = TaskStatus.RUNNING
        if self.current_step == 0 and self.plan.steps:
            self.current_step = 1

    def complete_step(self, step_id: int) -> None:
        if self.status != TaskStatus.RUNNING:
            raise ValueError("task must be running")
        if step_id != self.current_step:
            raise ValueError("step is not the current step")
        self.completed_steps.append(step_id)
        if step_id == len(self.plan.steps):
            self.status = TaskStatus.COMPLETE
            return
        self.current_step += 1

    def fail_step(self, step_id: int) -> None:
        if step_id != self.current_step:
            raise ValueError("step is not the current step")
        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)
        self.retry_counts[step_id] = self.retry_counts.get(step_id, 0) + 1
        self.status = TaskStatus.FAILED

    def block(self) -> None:
        self.status = TaskStatus.BLOCKED


class ToolRouter:
    """Route high-level agent kinds to registered execution providers."""

    def __init__(self) -> None:
        self._providers: dict[AgentKind, str] = {}

    def register(self, agent: AgentKind, provider: str) -> None:
        provider = provider.strip()
        if not provider:
            raise ValueError("provider cannot be empty")
        self._providers[agent] = provider

    def resolve(self, agent: AgentKind) -> str:
        try:
            return self._providers[agent]
        except KeyError as exc:
            raise LookupError(f"no provider registered for {agent.value}") from exc
