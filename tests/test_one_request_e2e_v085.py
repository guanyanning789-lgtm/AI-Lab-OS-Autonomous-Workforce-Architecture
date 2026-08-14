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
        skill_id="one-request",
        name="One Request",
        description="Run a two-step one-request workflow.",
        inputs=(SkillInputSpec("topic", "Topic"),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING),
        metadata={"triggers": "research,研究,pytest"},
        steps=(
            SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),
            SkillStepSpec("coding", PlannedTaskKind.VERIFY, AgentKind.CODING, "Verify {topic}.", depends_on=("research",)),
        ),
    ),))


def test_one_request_launches_hands_off_and_completes(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    calls: list[str] = []

    def executor(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "ok")

    result = launch_with_recovery_handoff(
        GoalIntakeRequest("请研究 pytest", goal_id="goal-one-request"),
        _registry(),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )

    final = store.load("goal-one-request")
    assert result.launch.supervisor.status == "cycle_limit"
    assert result.handed_off is True
    assert result.final_status == "complete"
    assert final.status == "complete"
    assert final.resume_cursor is None
    assert calls == [
        "goal-one-request-skill-001-research",
        "goal-one-request-skill-002-coding",
    ]
