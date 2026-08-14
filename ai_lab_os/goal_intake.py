from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_lab_os.goal_contract import GoalContract, GoalPriority


_GOAL_ID_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class GoalIntakeRequest:
    request: str
    goal_id: str | None = None
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    priority: GoalPriority = GoalPriority.NORMAL
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        request = self.request.strip()
        if not request:
            raise ValueError("goal intake request cannot be empty")
        if self.goal_id is not None and not self.goal_id.strip():
            raise ValueError("goal_id cannot be blank when provided")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata.items()):
            raise ValueError("goal intake metadata keys and values must be strings")
        object.__setattr__(self, "request", request)


@dataclass(frozen=True)
class GoalIntakeResult:
    contract: GoalContract
    source_request: str
    generated_goal_id: bool
    generated_success_criteria: bool


def _slug(text: str, *, limit: int = 48) -> str:
    normalized = text.casefold().encode("ascii", "ignore").decode("ascii")
    slug = _GOAL_ID_RE.sub("-", normalized).strip("-")
    return slug[:limit].rstrip("-") or "goal"


def _generated_goal_id(request: str, *, now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"goal-{stamp}-{_slug(request)}"


def intake_goal(
    request: GoalIntakeRequest,
    *,
    now: datetime | None = None,
) -> GoalIntakeResult:
    """Convert one natural-language request into a stable GoalContract.

    This layer is deliberately non-agentic: it validates and normalizes intake
    only. Skill selection, planning, execution, and recovery are wired in later
    V0.8 stages.
    """

    now = now or datetime.now(timezone.utc)
    generated_goal_id = request.goal_id is None
    goal_id = (
        _generated_goal_id(request.request, now=now)
        if generated_goal_id
        else request.goal_id.strip()
    )

    explicit_criteria = tuple(item.strip() for item in request.success_criteria if item.strip())
    generated_success_criteria = not explicit_criteria
    success_criteria = explicit_criteria or (
        "The requested outcome is completed and verified with evidence.",
    )

    constraints = tuple(item.strip() for item in request.constraints if item.strip())
    if len(constraints) != len(set(constraints)):
        raise ValueError("goal intake constraints cannot contain duplicates")

    metadata = dict(request.metadata)
    metadata.setdefault("intake_source", "natural_language")
    metadata.setdefault("intake_version", "0.8.1")
    metadata.setdefault("received_at", now.astimezone(timezone.utc).isoformat())

    contract = GoalContract(
        goal_id=goal_id,
        natural_language_goal=request.request,
        success_criteria=success_criteria,
        constraints=constraints,
        priority=request.priority,
        metadata=metadata,
    )
    return GoalIntakeResult(
        contract=contract,
        source_request=request.request,
        generated_goal_id=generated_goal_id,
        generated_success_criteria=generated_success_criteria,
    )
