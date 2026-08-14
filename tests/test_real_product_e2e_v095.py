from __future__ import annotations

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_service import GoalSubmissionRequest


def _skill() -> SkillContract:
    return SkillContract(
        skill_id="product-two-step",
        name="Product Two Step",
        description="Two safe research steps.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(
            SkillStepSpec("one", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "First {topic}."),
            SkillStepSpec("two", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Second {topic}.", depends_on=("one",)),
        ),
    )


def test_product_runtime_public_boundary_reaches_goal_complete(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    calls: list[str] = []

    def executor(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(
        SkillRegistry.from_skills((_skill(),)),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )
    result = runtime.submit(GoalSubmissionRequest(goal="研究 pytest", goal_id="goal-product"))
    snapshot = runtime.get_goal("goal-product")
    events = runtime.get_events("goal-product")

    assert result.status == "complete"
    assert result.handed_off is True
    assert snapshot.status == "complete"
    assert snapshot.progress_percent == 100
    assert snapshot.resume_cursor is None
    assert "GOAL_COMPLETE" in events
    assert calls == ["goal-product-skill-001-one", "goal-product-skill-002-two"]

    tick = runtime.tick()
    assert tick.recovery.actionable_goals == 0


def test_completed_product_goal_rejects_lifecycle_mutations(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(SkillRegistry.from_skills((_skill(),)), executor, store)
    runtime.submit(GoalSubmissionRequest(goal="研究 pytest", goal_id="goal-terminal"))

    for operation in (runtime.pause, runtime.cancel, runtime.resume):
        try:
            operation("goal-terminal")
        except ValueError:
            pass
        else:
            raise AssertionError("completed product goal must be terminal")
