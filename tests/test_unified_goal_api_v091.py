from __future__ import annotations

import pytest

from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_api import GoalSubmissionRequest, UnifiedGoalService


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills((
        SkillContract(
            skill_id="research-two-step",
            name="Research Two Step",
            description="Research and verify a topic.",
            inputs=(SkillInputSpec("topic", "Topic to research."),),
            required_agents=(AgentKind.RESEARCH, AgentKind.CODING),
            metadata={"triggers": "research,研究"},
            steps=(
                SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),
                SkillStepSpec("verify", PlannedTaskKind.VERIFY, AgentKind.CODING, "Verify {topic}.", depends_on=("research",)),
            ),
        ),
    ))


def test_submit_goal_runs_one_request_through_launch_and_recovery(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    seen: list[str] = []

    def executor(task):
        seen.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    service = UnifiedGoalService(
        _registry(),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )
    result = service.submit_goal(
        GoalSubmissionRequest("请研究 pytest", goal_id="goal-api")
    )

    assert result.goal_id == "goal-api"
    assert result.skill_id == "research-two-step"
    assert result.status == "complete"
    assert result.handed_off is True
    assert result.resume_cursor is None
    assert result.message == "Goal completed successfully."
    assert seen == [
        "goal-api-skill-001-research",
        "goal-api-skill-002-verify",
    ]
    assert store.load("goal-api").status == "complete"


def test_submission_request_rejects_empty_goal() -> None:
    with pytest.raises(ValueError, match="goal must not be empty"):
        GoalSubmissionRequest("   ")


def test_submission_request_rejects_invalid_priority() -> None:
    with pytest.raises(ValueError, match="priority"):
        GoalSubmissionRequest("research pytest", priority=101)


def test_duplicate_goal_id_fails_closed(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    service = UnifiedGoalService(_registry(), executor, store)
    request = GoalSubmissionRequest("请研究 pytest", goal_id="duplicate")
    service.submit_goal(request)
    with pytest.raises(ValueError, match="durable goal already exists"):
        service.submit_goal(request)
