from __future__ import annotations

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import extract_skill_inputs, route_skill_request, select_skill
from ai_lab_os.task_planner import PlannedTaskKind


def _research_skill() -> SkillContract:
    return SkillContract(
        skill_id="research-topic",
        name="Research Topic",
        description="Research a topic on the web and return evidence.",
        inputs=(SkillInputSpec("topic", "Topic to research."),),
        required_agents=(AgentKind.RESEARCH,),
        permissions=("web.search",),
        metadata={"triggers": "research,查资料,研究"},
        steps=(
            SkillStepSpec(
                step_id="research",
                kind=PlannedTaskKind.ANALYZE,
                agent=AgentKind.RESEARCH,
                description_template="Research {topic} and return evidence.",
                metadata_templates={"query": "{topic}"},
            ),
        ),
    )


def _coding_skill() -> SkillContract:
    return SkillContract(
        skill_id="verify-code",
        name="Verify Code",
        description="Run coding verification and tests for a repository change.",
        inputs=(SkillInputSpec("task", "Coding task to verify."),),
        required_agents=(AgentKind.CODING,),
        metadata={"triggers": "pytest,test code,跑测试"},
        steps=(
            SkillStepSpec(
                step_id="verify",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.CODING,
                description_template="Verify {task}.",
            ),
        ),
    )


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills((_research_skill(), _coding_skill()))


def test_select_skill_prefers_explicit_trigger() -> None:
    selected = select_skill("请帮我研究 pytest 的 fixture", _registry())
    assert selected.skill.skill_id == "research-topic"
    assert selected.score >= 12


def test_select_skill_fails_closed_when_no_skill_matches() -> None:
    with pytest.raises(LookupError, match="no registered skill matched"):
        select_skill("播放一首钢琴曲", _registry())


def test_select_skill_rejects_ambiguous_top_score() -> None:
    first = _research_skill()
    second = SkillContract(
        skill_id="research-alt",
        name="Research Alternate",
        description=first.description,
        inputs=first.inputs,
        required_agents=first.required_agents,
        metadata={"triggers": "research"},
        steps=first.steps,
    )
    registry = SkillRegistry.from_skills((first, second))
    with pytest.raises(LookupError, match="ambiguous skill request"):
        select_skill("research", registry)


def test_extract_single_required_input_uses_full_request_when_not_explicit() -> None:
    skill = _research_skill()
    request = "请帮我研究 pytest fixture"
    assert extract_skill_inputs(request, skill) == {"topic": request}


def test_extract_explicit_name_value_input() -> None:
    assert extract_skill_inputs("research topic=pytest fixtures", _research_skill()) == {
        "topic": "pytest fixtures"
    }


def test_route_skill_request_selects_binds_and_compiles() -> None:
    routed = route_skill_request(
        "research topic=pytest fixtures",
        _registry(),
        goal_id="goal-skill-route",
    )
    assert routed.selection.skill.skill_id == "research-topic"
    assert routed.extracted_inputs == {"topic": "pytest fixtures"}
    assert routed.compiled.plan.goal_id == "goal-skill-route"
    assert routed.compiled.plan.tasks[0].agent is AgentKind.RESEARCH
    assert routed.compiled.plan.tasks[0].metadata["query"] == "pytest fixtures"
