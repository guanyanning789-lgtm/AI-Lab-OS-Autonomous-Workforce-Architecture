from __future__ import annotations

import pytest

from ai_lab_os.agent_router import AgentRouter
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import TaskExecutionResult
from ai_lab_os.task_planner import PlannedTask, PlannedTaskKind


def _task(agent: AgentKind) -> PlannedTask:
    return PlannedTask(
        task_id=f"task-{agent.value}",
        goal_id="goal-router",
        sequence=1,
        kind=PlannedTaskKind.ANALYZE,
        description=f"Run {agent.value} task",
        agent=agent,
    )


def _executor(label: str):
    def run(task: PlannedTask) -> TaskExecutionResult:
        return TaskExecutionResult(success=True, message=f"{label}:{task.task_id}")

    return run


def test_core_agents_route_to_distinct_executors() -> None:
    router = AgentRouter.with_core_agents(
        coding=_executor("coding"),
        research=_executor("research"),
        computer=_executor("computer"),
    )

    assert router.execute(_task(AgentKind.CODING)).message == "coding:task-coding"
    assert router.execute(_task(AgentKind.RESEARCH)).message == "research:task-research"
    assert router.execute(_task(AgentKind.COMPUTER)).message == "computer:task-computer"


def test_unknown_agent_fails_closed() -> None:
    router = AgentRouter()

    with pytest.raises(LookupError, match="no executor registered"):
        router.execute(_task(AgentKind.CODING))


def test_duplicate_registration_is_rejected_but_replace_is_explicit() -> None:
    router = AgentRouter()
    router.register(AgentKind.CODING, _executor("one"))

    with pytest.raises(ValueError, match="already registered"):
        router.register(AgentKind.CODING, _executor("two"))

    router.replace(AgentKind.CODING, _executor("two"))
    assert router.execute(_task(AgentKind.CODING)).message == "two:task-coding"


def test_supports_reports_registered_agents() -> None:
    router = AgentRouter()
    router.register(AgentKind.RESEARCH, _executor("research"))

    assert router.supports(AgentKind.RESEARCH) is True
    assert router.supports(AgentKind.CODING) is False
