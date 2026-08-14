from __future__ import annotations

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.skill_compiler import compile_skill_plan
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.task_planner import PlannedTaskKind


def _skill() -> SkillContract:
    return SkillContract(
        skill_id="research-implement-verify",
        name="Research Implement Verify",
        description="Compile one reusable multi-agent skill.",
        inputs=(
            SkillInputSpec("topic", "Topic to research."),
            SkillInputSpec("window_title", "Target window.", required=False, default="Notepad"),
        ),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        permissions=("web.search", "code.verify", "computer.mock"),
        success_criteria=("The skill goal is completed for {topic}.",),
        steps=(
            SkillStepSpec(
                step_id="research",
                kind=PlannedTaskKind.ANALYZE,
                agent=AgentKind.RESEARCH,
                description_template="Research {topic} and return evidence.",
                metadata_templates={"query": "{topic}"},
            ),
            SkillStepSpec(
                step_id="code",
                kind=PlannedTaskKind.IMPLEMENT,
                agent=AgentKind.CODING,
                description_template="Verify the local implementation for {topic}.",
                depends_on=("research",),
                success_criteria=("Configured tests pass for {topic}.",),
            ),
            SkillStepSpec(
                step_id="verify",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.COMPUTER,
                description_template="Verify {topic} in {window_title}.",
                depends_on=("code",),
                metadata_templates={
                    "action": "click",
                    "args_json": "{}",
                    "window_title": "{window_title}",
                },
            ),
        ),
    )


def test_compile_skill_plan_binds_inputs_and_preserves_agent_order() -> None:
    compiled = compile_skill_plan(_skill(), {"topic": "pytest"}, goal_id="goal-001")

    assert compiled.skill_id == "research-implement-verify"
    assert compiled.bound_inputs == {"topic": "pytest", "window_title": "Notepad"}
    assert compiled.plan.planner_version == "v0.5.3-skill-compiler"
    assert [task.agent for task in compiled.plan.tasks] == [
        AgentKind.RESEARCH,
        AgentKind.CODING,
        AgentKind.COMPUTER,
    ]
    assert compiled.plan.tasks[0].metadata["query"] == "pytest"
    assert compiled.plan.tasks[2].metadata["window_title"] == "Notepad"


def test_compile_skill_plan_translates_step_dependencies_to_task_ids() -> None:
    tasks = compile_skill_plan(_skill(), {"topic": "pytest"}, goal_id="goal-001").plan.tasks

    assert tasks[0].depends_on == ()
    assert tasks[1].depends_on == (tasks[0].task_id,)
    assert tasks[2].depends_on == (tasks[1].task_id,)


def test_compile_skill_plan_carries_skill_permissions_and_identity() -> None:
    task = compile_skill_plan(_skill(), {"topic": "pytest"}, goal_id="goal-001").plan.tasks[0]

    assert task.metadata["skill_id"] == "research-implement-verify"
    assert task.metadata["skill_version"] == "0.5.1"
    assert task.metadata["skill_permissions"] == "web.search,code.verify,computer.mock"


def test_compile_skill_plan_preserves_literal_json_metadata() -> None:
    task = compile_skill_plan(_skill(), {"topic": "pytest"}, goal_id="goal-001").plan.tasks[2]
    assert task.metadata["args_json"] == "{}"


def test_compile_skill_plan_preserves_literal_json_object_with_fields() -> None:
    skill = SkillContract(
        skill_id="json-metadata",
        name="JSON Metadata",
        description="Preserve JSON metadata literals.",
        inputs=(),
        required_agents=(AgentKind.COMPUTER,),
        steps=(
            SkillStepSpec(
                step_id="computer",
                kind=PlannedTaskKind.VERIFY,
                agent=AgentKind.COMPUTER,
                description_template="Verify.",
                metadata_templates={"args_json": '{"target":"100,100"}'},
            ),
        ),
    )
    task = compile_skill_plan(skill, {}, goal_id="goal-json").plan.tasks[0]
    assert task.metadata["args_json"] == '{"target":"100,100"}'


def test_compile_skill_plan_rejects_missing_inputs() -> None:
    with pytest.raises(ValueError, match="missing required skill input: topic"):
        compile_skill_plan(_skill(), {}, goal_id="goal-001")


def test_compile_skill_plan_rejects_unknown_template_variable() -> None:
    skill = SkillContract(
        skill_id="bad-template",
        name="Bad Template",
        description="Bad template skill.",
        inputs=(),
        required_agents=(AgentKind.RESEARCH,),
        steps=(
            SkillStepSpec(
                step_id="research",
                kind=PlannedTaskKind.ANALYZE,
                agent=AgentKind.RESEARCH,
                description_template="Research {missing}.",
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown skill template variable: missing"):
        compile_skill_plan(skill, {}, goal_id="goal-001")


def test_skill_contract_rejects_step_using_undeclared_agent() -> None:
    with pytest.raises(ValueError, match="uses undeclared agent: computer"):
        SkillContract(
            skill_id="bad-agent",
            name="Bad Agent",
            description="Bad agent skill.",
            inputs=(),
            required_agents=(AgentKind.RESEARCH,),
            steps=(
                SkillStepSpec(
                    step_id="verify",
                    kind=PlannedTaskKind.VERIFY,
                    agent=AgentKind.COMPUTER,
                    description_template="Verify.",
                ),
            ),
        )
