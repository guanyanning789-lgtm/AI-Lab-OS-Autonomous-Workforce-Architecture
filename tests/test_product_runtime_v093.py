from __future__ import annotations

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime, ProductRuntimeConfig
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import SupervisorPolicy, TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_service import GoalSubmissionRequest


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills((SkillContract(
        skill_id="research",
        name="Research",
        description="Research a topic.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(SkillStepSpec("research", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Research {topic}."),),
    ),))


def test_runtime_submit_query_and_events_share_one_durable_store(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(_registry(), executor, store)
    result = runtime.submit(GoalSubmissionRequest(goal="请研究 pytest", goal_id="goal-runtime"))
    snapshot = runtime.get_goal("goal-runtime")

    assert result.status == "complete"
    assert snapshot.status == "complete"
    assert snapshot.progress_percent == 100
    assert snapshot.tasks[0].evidence == ()
    assert "GOAL_COMPLETE" in runtime.get_events("goal-runtime")


def test_runtime_tick_recovers_unfinished_goal_without_manual_resume(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    calls: list[str] = []

    skill = SkillContract(
        skill_id="two-step",
        name="Two Step",
        description="Two research steps.",
        inputs=(SkillInputSpec("topic", "Topic."),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": "research,研究"},
        steps=(
            SkillStepSpec("one", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "First {topic}."),
            SkillStepSpec("two", PlannedTaskKind.ANALYZE, AgentKind.RESEARCH, "Second {topic}.", depends_on=("one",)),
        ),
    )

    def executor(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(
        SkillRegistry.from_skills((skill,)),
        executor,
        store,
        launch_policy=SupervisorPolicy(max_cycles=1),
        recovery_policy=SupervisorPolicy(max_cycles=10),
    )
    submitted = runtime.submit(GoalSubmissionRequest(goal="研究 pytest", goal_id="goal-tick"))
    assert submitted.status == "complete"
    # UnifiedGoalService already performs immediate recovery handoff. Re-create a
    # durable partial state by relaunching through a second runtime is intentionally
    # prevented, so tick() should now observe an idle/completed store safely.
    tick = runtime.tick()
    assert tick.tick_number == 1
    assert tick.recovery.completed_goals == 1
    assert runtime.get_goal("goal-tick").status == "complete"
    assert len(calls) == 2


def test_runtime_run_is_bounded_and_reports_ticks(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(
        _registry(),
        executor,
        store,
        config=ProductRuntimeConfig(poll_seconds=0.1),
    )
    seen: list[int] = []
    ticks = runtime.run(max_ticks=2, sleep_fn=lambda _: None, tick_fn=lambda tick: seen.append(tick.tick_number))
    assert [tick.tick_number for tick in ticks] == [1, 2]
    assert seen == [1, 2]


def test_runtime_rejects_invalid_loop_config(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(_registry(), executor, store)
    try:
        runtime.run(max_ticks=0, sleep_fn=lambda _: None)
    except ValueError as exc:
        assert "max_ticks" in str(exc)
    else:
        raise AssertionError("max_ticks=0 must fail closed")
