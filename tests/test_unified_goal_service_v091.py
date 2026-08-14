from __future__ import annotations

from ai_lab_os.goal_contract import GoalPriority
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_service import GoalSubmissionRequest, UnifiedGoalService


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


def test_submit_goal_shapes_product_result_and_persists(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    service = UnifiedGoalService(_registry(), executor, store)
    result = service.submit_goal(GoalSubmissionRequest(
        goal="请研究 pytest",
        goal_id="goal-service",
        success_criteria=("research complete",),
        constraints=("safe only",),
        priority=GoalPriority.HIGH,
        metadata={"source": "test"},
    ))

    saved = store.load("goal-service")
    assert result.goal_id == "goal-service"
    assert result.skill_id == "research"
    assert result.status == "complete"
    assert result.handed_off is False
    assert result.resume_cursor is None
    assert result.message == "All planned tasks completed successfully."
    assert saved.status == "complete"


def test_submit_goal_uses_recovery_handoff_for_partial_launch(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    calls: list[str] = []

    def executor(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    skill = SkillContract(
        skill_id="two-step",
        name="Two Step",
        description="Research twice.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(
            SkillStepSpec("one", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "First {topic}."),
            SkillStepSpec("two", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Second {topic}.", depends_on=("one",)),
        ),
    )
    service = UnifiedGoalService(
        SkillRegistry.from_skills((skill,)),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )
    result = service.submit_goal(GoalSubmissionRequest(goal="研究 pytest", goal_id="goal-handoff"))

    assert result.status == "complete"
    assert result.handed_off is True
    assert result.resume_cursor is None
    assert calls == [
        "goal-handoff-skill-001-one",
        "goal-handoff-skill-002-two",
    ]


def test_submission_rejects_blank_goal() -> None:
    try:
        GoalSubmissionRequest(goal="   ")
    except ValueError as exc:
        assert "goal must not be empty" in str(exc)
    else:
        raise AssertionError("blank goal should fail")
