from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ai_lab_os.goal_contract import GoalContract
from ai_lab_os.models import AgentKind


class PlannedTaskKind(str, Enum):
    ANALYZE = "analyze"
    IMPLEMENT = "implement"
    VERIFY = "verify"


@dataclass(frozen=True)
class PlannedTask:
    task_id: str
    goal_id: str
    sequence: int
    kind: PlannedTaskKind
    description: str
    agent: AgentKind
    success_criteria: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        task_id = self.task_id.strip()
        goal_id = self.goal_id.strip()
        description = self.description.strip()
        criteria = tuple(item.strip() for item in self.success_criteria if item.strip())
        dependencies = tuple(item.strip() for item in self.depends_on if item.strip())

        if not task_id:
            raise ValueError("task_id cannot be empty")
        if not goal_id:
            raise ValueError("goal_id cannot be empty")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")
        if not description:
            raise ValueError("description cannot be empty")
        if task_id in dependencies:
            raise ValueError("task cannot depend on itself")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("depends_on cannot contain duplicates")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata.items()):
            raise ValueError("metadata keys and values must be strings")

        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "goal_id", goal_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "success_criteria", criteria)
        object.__setattr__(self, "depends_on", dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_id": self.goal_id,
            "sequence": self.sequence,
            "kind": self.kind.value,
            "description": self.description,
            "agent": self.agent.value,
            "success_criteria": list(self.success_criteria),
            "depends_on": list(self.depends_on),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TaskPlanContract:
    goal_id: str
    tasks: tuple[PlannedTask, ...]
    planner_version: str = "v0.3.2"

    def __post_init__(self) -> None:
        goal_id = self.goal_id.strip()
        if not goal_id:
            raise ValueError("goal_id cannot be empty")
        if not self.tasks:
            raise ValueError("task plan must contain at least one task")

        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task ids must be unique")
        if any(task.goal_id != goal_id for task in self.tasks):
            raise ValueError("every task must belong to the plan goal_id")

        sequences = [task.sequence for task in self.tasks]
        if sequences != list(range(1, len(self.tasks) + 1)):
            raise ValueError("task sequence must be contiguous starting at 1")

        known_ids = set(task_ids)
        for task in self.tasks:
            unknown = sorted(set(task.depends_on) - known_ids)
            if unknown:
                raise ValueError(f"task {task.task_id} depends on unknown tasks: {', '.join(unknown)}")
            later_or_self = {
                dependency
                for dependency in task.depends_on
                if task_ids.index(dependency) >= task_ids.index(task.task_id)
            }
            if later_or_self:
                raise ValueError("task dependencies must point only to earlier tasks")

        object.__setattr__(self, "goal_id", goal_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "planner_version": self.planner_version,
            "tasks": [task.to_dict() for task in self.tasks],
        }


def plan_goal(goal: GoalContract) -> TaskPlanContract:
    """Build the first explicit supervisor plan without executing any task.

    V0.3.2 intentionally keeps planning deterministic. A later supervisor/model
    planner can replace this strategy while preserving the TaskPlanContract.
    """

    prefix = goal.goal_id
    analyze_id = f"{prefix}-task-001"
    implement_id = f"{prefix}-task-002"
    verify_id = f"{prefix}-task-003"

    constraints = " ".join(goal.constraints)
    constraint_suffix = f" Constraints: {constraints}" if constraints else ""

    tasks = (
        PlannedTask(
            task_id=analyze_id,
            goal_id=goal.goal_id,
            sequence=1,
            kind=PlannedTaskKind.ANALYZE,
            description=(
                f"Analyze the goal, repository context, risks, and smallest safe implementation path for: "
                f"{goal.natural_language_goal}.{constraint_suffix}"
            ),
            agent=AgentKind.CODING,
            success_criteria=("A concrete implementation path and verification strategy are identified.",),
        ),
        PlannedTask(
            task_id=implement_id,
            goal_id=goal.goal_id,
            sequence=2,
            kind=PlannedTaskKind.IMPLEMENT,
            description=f"Implement the smallest safe change required to achieve: {goal.natural_language_goal}.",
            agent=AgentKind.CODING,
            success_criteria=goal.success_criteria,
            depends_on=(analyze_id,),
        ),
        PlannedTask(
            task_id=verify_id,
            goal_id=goal.goal_id,
            sequence=3,
            kind=PlannedTaskKind.VERIFY,
            description="Verify the implementation against every goal success criterion and report evidence.",
            agent=AgentKind.CODING,
            success_criteria=goal.success_criteria,
            depends_on=(implement_id,),
        ),
    )
    return TaskPlanContract(goal_id=goal.goal_id, tasks=tasks)


def write_task_plan(path: str | Path, plan: TaskPlanContract) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
