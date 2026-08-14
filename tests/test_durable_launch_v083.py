from __future__ import annotations

import pytest

from ai_lab_os.durable_launch import launch_goal
from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills((SkillContract(
        skill_id="research",
        name="Research",
        description="Research a topic.",
        inputs=(SkillInputSpec("topic", "Topic to research."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),),
    ),))


def test_launch_routes_persists_and_executes_one_request(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    seen: list[str] = []

    def executor(task):
        seen.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, message="done")

    result = launch_goal(
        GoalIntakeRequest("请研究 pytest", goal_id="goal-launch"),
        _registry(),
        executor,
        store,
    )
    saved = store.load("goal-launch")
    assert result.goal_id == "goal-launch"
    assert result.routed.routed.selection.skill.skill_id == "research"
    assert result.supervisor.status == "complete"
    assert saved.status == "complete"
    assert saved.resume_cursor is None
    assert seen == ["goal-launch-skill-001-research"]


def test_launch_rejects_existing_durable_goal_instead_of_overwriting(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, message="done")

    request = GoalIntakeRequest("请研究 pytest", goal_id="goal-duplicate")
    launch_goal(request, _registry(), executor, store)
    with pytest.raises(ValueError, match="durable goal already exists"):
        launch_goal(request, _registry(), executor, store)
