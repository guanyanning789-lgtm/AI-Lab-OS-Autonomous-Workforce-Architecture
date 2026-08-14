from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.goal_intake import GoalIntakeRequest, GoalIntakeResult, intake_goal
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import RoutedSkillRequest, route_skill_request


@dataclass(frozen=True)
class IntakeRoutingResult:
    intake: GoalIntakeResult
    routed: RoutedSkillRequest

    @property
    def goal_id(self) -> str:
        return self.intake.contract.goal_id

    @property
    def skill_id(self) -> str:
        return self.routed.selection.skill.skill_id


def intake_and_route(
    request: GoalIntakeRequest,
    registry: SkillRegistry,
    *,
    min_score: int = 2,
) -> IntakeRoutingResult:
    """Normalize one natural-language goal, select a Skill, and compile its TaskPlan.

    This stage still does not execute anything. It composes the already-proven
    V0.8.1 Goal Intake and V0.5 Skill routing/compiler contracts into one stable
    orchestration boundary for V0.8.3 durable launch.
    """

    intake = intake_goal(request)
    routed = route_skill_request(
        intake.source_request,
        registry,
        goal_id=intake.contract.goal_id,
        min_score=min_score,
    )
    if routed.compiled.plan.goal_id != intake.contract.goal_id:
        raise RuntimeError("compiled Skill plan goal_id does not match intake goal_id")
    return IntakeRoutingResult(intake=intake, routed=routed)
