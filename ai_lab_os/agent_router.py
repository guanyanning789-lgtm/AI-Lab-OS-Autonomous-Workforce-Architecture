from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult
from ai_lab_os.task_planner import PlannedTask


TaskExecutor = Callable[[PlannedTask], TaskExecutionResult]


@dataclass
class AgentRouter:
    executors: dict[AgentKind, TaskExecutor] = field(default_factory=dict)

    def register(self, agent: AgentKind, executor: TaskExecutor) -> None:
        if agent in self.executors:
            raise ValueError(f"executor already registered for agent: {agent.value}")
        self.executors[agent] = executor

    def replace(self, agent: AgentKind, executor: TaskExecutor) -> None:
        self.executors[agent] = executor

    def supports(self, agent: AgentKind) -> bool:
        return agent in self.executors

    def executor_for(self, agent: AgentKind) -> TaskExecutor:
        try:
            return self.executors[agent]
        except KeyError as exc:
            raise LookupError(f"no executor registered for agent: {agent.value}") from exc

    def execute(self, task: PlannedTask) -> TaskExecutionResult:
        return self.executor_for(task.agent)(task)

    @classmethod
    def with_core_agents(
        cls,
        *,
        coding: TaskExecutor,
        research: TaskExecutor,
        computer: TaskExecutor,
    ) -> "AgentRouter":
        router = cls()
        router.register(AgentKind.CODING, coding)
        router.register(AgentKind.RESEARCH, research)
        router.register(AgentKind.COMPUTER, computer)
        return router
