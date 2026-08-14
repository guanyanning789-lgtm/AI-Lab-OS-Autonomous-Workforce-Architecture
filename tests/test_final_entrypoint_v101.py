from __future__ import annotations

import pytest

from ai_lab_os.final_entrypoint import FinalNaturalLanguageEntrypoint
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind


def _runtime(tmp_path) -> ProductRuntime:
    skill = SkillContract(
        skill_id="research",
        name="Research",
        description="Research a topic.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),),
    )

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    return ProductRuntime(
        SkillRegistry.from_skills((skill,)),
        executor,
        JsonGoalStore(tmp_path / "goals.json"),
    )


def test_one_sentence_reaches_final_result_without_internal_plumbing(tmp_path) -> None:
    entry = FinalNaturalLanguageEntrypoint(_runtime(tmp_path))
    result = entry.run("请研究 pytest", goal_id="v101-goal")
    assert result.goal_id == "v101-goal"
    assert result.skill_id == "research"
    assert result.status == "complete"
    assert result.progress_percent == 100
    assert result.resume_cursor is None


def test_blank_sentence_fails_closed(tmp_path) -> None:
    entry = FinalNaturalLanguageEntrypoint(_runtime(tmp_path))
    with pytest.raises(ValueError, match="request must not be empty"):
        entry.run("   ")
