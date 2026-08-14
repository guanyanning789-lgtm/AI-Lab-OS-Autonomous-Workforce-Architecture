from __future__ import annotations

from ai_lab_os.goal_intake import GoalIntakeRequest
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.recovery_handoff import launch_with_recovery_handoff
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills((SkillContract(
        skill_id="two-step",
        name="Two Step",
        description="Research and verify.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING),
        metadata={"triggers": "research,研究,verify,验证"},
        steps=(
            SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),
            SkillStepSpec("verify", PlannedTaskKind.VERIFY, AgentKind.CODING, "Verify {topic}.", depends_on=("research",)),
        ),
    ),))


def test_handoff_recovers_cycle_limited_launch_without_manual_resume(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    seen: list[str] = []

    def executor(task):
        seen.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    result = launch_with_recovery_handoff(
        GoalIntakeRequest("请研究并验证 pytest", goal_id="goal-handoff"),
        _registry(),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )

    saved = store.load("goal-handoff")
    assert result.launch.supervisor.status == "cycle_limit"
    assert result.handed_off is True
    assert result.recovery is not None
    assert result.final_status == "complete"
    assert saved.status == "complete"
    assert saved.resume_cursor is None
    assert seen == [
        "goal-handoff-skill-001-research",
        "goal-handoff-skill-002-verify",
    ]


def test_completed_launch_does_not_enter_recovery(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    result = launch_with_recovery_handoff(
        GoalIntakeRequest("请研究并验证 pytest", goal_id="goal-direct"),
        _registry(),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=10),
    )

    assert result.launch.supervisor.status == "complete"
    assert result.handed_off is False
    assert result.recovery is None
    assert result.final_status == "complete"
