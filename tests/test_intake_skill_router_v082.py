from __future__ import annotations

from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.intake_skill_router import intake_and_route
from ai_lab_os.models import AgentKind
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.task_planner import PlannedTaskKind


def _registry() -> SkillRegistry:
    skill = SkillContract(
        skill_id="research-verify",
        name="Research Verify",
        description="Research a technical topic and verify it.",
        inputs=(SkillInputSpec("topic", "Technical topic to research."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "研究,research,pytest"},
        steps=(
            SkillStepSpec(
                "research",
                PlannedTaskKind.ANALYZE,
                AgentKind.RESEARCH,
                "Research {topic}.",
                metadata_templates={"query": "{topic}"},
            ),
        ),
    )
    return SkillRegistry.from_skills((skill,))


def test_intake_and_route_preserves_one_goal_id_across_contract_and_plan() -> None:
    result = intake_and_route(
        GoalIntakeRequest(
            request="请研究 pytest fixture",
            goal_id="goal-v082",
        ),
        _registry(),
    )
    assert result.goal_id == "goal-v082"
    assert result.skill_id == "research-verify"
    assert result.intake.contract.goal_id == result.routed.compiled.plan.goal_id
    assert result.routed.extracted_inputs["topic"] == "请研究 pytest fixture"


def test_intake_and_route_generates_goal_id_when_not_provided() -> None:
    result = intake_and_route(GoalIntakeRequest(request="research pytest fixture"), _registry())
    assert result.goal_id.startswith("goal-")
    assert result.routed.compiled.plan.goal_id == result.goal_id


def test_intake_and_route_fails_closed_when_no_skill_matches() -> None:
    import pytest

    with pytest.raises(LookupError, match="no registered skill matched"):
        intake_and_route(
            GoalIntakeRequest(request="compose an orchestral symphony"),
            _registry(),
            min_score=20,
        )
