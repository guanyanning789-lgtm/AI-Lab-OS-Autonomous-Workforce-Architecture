from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentKind(str, Enum):
    CODING = "coding"
    RESEARCH = "research"
    COMPUTER = "computer"
    SKILL = "skill"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Goal:
    text: str
    success_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("goal text cannot be empty")


@dataclass(frozen=True)
class TaskStep:
    step_id: int
    description: str
    agent: AgentKind
    skill: str | None = None
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if self.step_id < 1:
            raise ValueError("step_id must be >= 1")
        if not self.description.strip():
            raise ValueError("step description cannot be empty")


@dataclass(frozen=True)
class TaskPlan:
    goal: Goal
    steps: tuple[TaskStep, ...]
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ids = [step.step_id for step in self.steps]
        if ids != list(range(1, len(ids) + 1)):
            raise ValueError("step ids must be contiguous starting at 1")
