from __future__ import annotations

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.product_service import ProductServiceHost
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
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


def test_service_start_stop_restart_preserves_durable_goal(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    def factory() -> ProductRuntime:
        return ProductRuntime(_registry(), executor, store)

    host = ProductServiceHost(factory)
    started = host.start(recover=False)
    assert started.running is True
    assert started.generation == 1

    submitted = host.runtime.submit(GoalSubmissionRequest(goal="请研究 pytest", goal_id="service-goal"))
    assert submitted.status == "complete"

    stopped = host.stop()
    assert stopped.running is False
    with pytest.raises(RuntimeError, match="not running"):
        _ = host.runtime

    restarted = host.start(recover=True)
    assert restarted.running is True
    assert restarted.generation == 2
    assert restarted.last_recovery_tick == 1
    assert host.runtime.get_goal("service-goal").status == "complete"


def test_restart_replaces_process_local_runtime_but_keeps_store(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    host = ProductServiceHost(lambda: ProductRuntime(_registry(), executor, store))
    host.start(recover=False)
    first = host.runtime
    health = host.restart(recover=False)
    second = host.runtime
    assert first is not second
    assert health.generation == 2


def test_service_lifecycle_fails_closed(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")

    def executor(task):
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    host = ProductServiceHost(lambda: ProductRuntime(_registry(), executor, store))
    with pytest.raises(RuntimeError, match="not running"):
        host.stop()
    host.start(recover=False)
    with pytest.raises(RuntimeError, match="already running"):
        host.start()
