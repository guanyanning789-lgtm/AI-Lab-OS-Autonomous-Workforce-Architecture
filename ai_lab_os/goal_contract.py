from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class GoalStatus(str, Enum):
    RECEIVED = "received"
    PLANNING = "planning"
    ACTIVE = "active"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETE = "complete"


class GoalPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GoalContract:
    goal_id: str
    natural_language_goal: str
    success_criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    priority: GoalPriority = GoalPriority.NORMAL
    status: GoalStatus = GoalStatus.RECEIVED
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        goal_id = self.goal_id.strip()
        goal = self.natural_language_goal.strip()
        criteria = tuple(item.strip() for item in self.success_criteria if item.strip())
        constraints = tuple(item.strip() for item in self.constraints if item.strip())

        if not goal_id:
            raise ValueError("goal_id cannot be empty")
        if not goal:
            raise ValueError("natural_language_goal cannot be empty")
        if not criteria:
            raise ValueError("success_criteria must contain at least one non-empty item")
        if len(criteria) != len(set(criteria)):
            raise ValueError("success_criteria cannot contain duplicates")
        if len(constraints) != len(set(constraints)):
            raise ValueError("constraints cannot contain duplicates")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata.items()):
            raise ValueError("metadata keys and values must be strings")

        object.__setattr__(self, "goal_id", goal_id)
        object.__setattr__(self, "natural_language_goal", goal)
        object.__setattr__(self, "success_criteria", criteria)
        object.__setattr__(self, "constraints", constraints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "natural_language_goal": self.natural_language_goal,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "priority": self.priority.value,
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoalContract":
        allowed = {
            "goal_id",
            "natural_language_goal",
            "success_criteria",
            "constraints",
            "priority",
            "status",
            "metadata",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"unknown goal contract fields: {', '.join(unknown)}")

        criteria = payload.get("success_criteria")
        constraints = payload.get("constraints", [])
        metadata = payload.get("metadata", {})
        if not isinstance(criteria, list) or not all(isinstance(item, str) for item in criteria):
            raise ValueError("success_criteria must be a list of strings")
        if not isinstance(constraints, list) or not all(isinstance(item, str) for item in constraints):
            raise ValueError("constraints must be a list of strings")
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")

        try:
            priority = GoalPriority(str(payload.get("priority", GoalPriority.NORMAL.value)))
        except ValueError as exc:
            raise ValueError("invalid goal priority") from exc
        try:
            status = GoalStatus(str(payload.get("status", GoalStatus.RECEIVED.value)))
        except ValueError as exc:
            raise ValueError("invalid goal status") from exc

        return cls(
            goal_id=str(payload.get("goal_id", "")),
            natural_language_goal=str(payload.get("natural_language_goal", "")),
            success_criteria=tuple(criteria),
            constraints=tuple(constraints),
            priority=priority,
            status=status,
            metadata=metadata,
        )


def load_goal_contract(path: str | Path) -> GoalContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("goal contract JSON must contain an object")
    return GoalContract.from_dict(payload)


def write_goal_contract(path: str | Path, contract: GoalContract) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(contract.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
