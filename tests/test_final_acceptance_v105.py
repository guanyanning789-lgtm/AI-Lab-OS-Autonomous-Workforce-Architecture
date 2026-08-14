from __future__ import annotations

from ai_lab_os.approval_boundary import ApprovalAwareExecutor, ApprovalService
from ai_lab_os.final_entrypoint import FinalNaturalLanguageEntrypoint
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.product_service import ProductServiceHost
from ai_lab_os.progress_report import ProgressReportService, render_progress
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind


def _registry() -> SkillRegistry:
    skill = SkillContract(
        skill_id="v1-final-workforce",
        name="V1 Final Workforce",
        description="Research, code and perform a gated computer verification.",
        inputs=(SkillInputSpec("topic", "User goal."),),
        required_agents=(AgentKind.RESEARCH, AgentKind.CODING, AgentKind.COMPUTER),
        metadata={"triggers": "研究,research,代码,code,电脑,computer,验证,verify"},
        steps=(
            SkillStepSpec(
                "research",
                PlannedTaskKind.ANALYZE,
                AgentKind.RESEARCH,
                "Research {topic}.",
            ),
            SkillStepSpec(
                "coding",
                PlannedTaskKind.VERIFY,
                AgentKind.CODING,
                "Verify code for {topic}.",
                depends_on=("research",),
            ),
            SkillStepSpec(
                "computer",
                PlannedTaskKind.VERIFY,
                AgentKind.COMPUTER,
                "Perform final computer verification for {topic}.",
                depends_on=("coding",),
                metadata_templates={"action": "click"},
            ),
        ),
    )
    return SkillRegistry.from_skills((skill,))


def test_v1_final_acceptance_one_sentence_restart_approval_and_goal_complete(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    executed: list[str] = []

    def inner(task):
        executed.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, f"{task.agent.value} completed")

    def runtime_factory() -> ProductRuntime:
        approvals = ApprovalService(store)
        gated = ApprovalAwareExecutor(inner, approvals, real_computer_actions_enabled=True)
        return ProductRuntime(
            _registry(),
            gated,
            store,
            approval_service=approvals,
        )

    host = ProductServiceHost(runtime_factory)
    first_health = host.start(recover=False)
    assert first_health.running is True
    assert first_health.generation == 1

    entry = FinalNaturalLanguageEntrypoint(host.runtime)
    first = entry.run(
        "请研究测试流程、验证代码，并完成电脑验证",
        goal_id="v105-final-goal",
    )

    assert first.status == "approval_required"
    assert executed == [
        "v105-final-goal-skill-001-research",
        "v105-final-goal-skill-002-coding",
    ]

    waiting_report = ProgressReportService(host.runtime).get(first.goal_id)
    assert waiting_report.status == "approval_required"
    assert waiting_report.progress_percent == 66
    rendered_waiting = render_progress(waiting_report)
    assert "PROGRESS" in rendered_waiting
    assert "66%" in rendered_waiting

    host.stop()
    restarted = host.start(recover=True)
    assert restarted.running is True
    assert restarted.generation == 2
    # Awaiting approval must survive service restart, while the approval grant
    # itself must not be invented or replayed by recovery.
    still_waiting = host.runtime.get_goal(first.goal_id)
    assert still_waiting.status == "approval_required"
    assert still_waiting.tasks[-1].status == "awaiting_approval"
    assert executed[-1].endswith("coding")

    host.runtime.approve(first.goal_id, still_waiting.resume_cursor or "")
    tick = host.runtime.tick()
    assert tick.recovery.actionable_goals == 1

    final = host.runtime.get_goal(first.goal_id)
    report = ProgressReportService(host.runtime).get(first.goal_id)
    assert final.status == "complete"
    assert final.progress_percent == 100
    assert final.resume_cursor is None
    assert report.final_result == "GOAL_COMPLETE"
    assert "GOAL_COMPLETE" in final.events
    assert any(event.startswith("APPROVAL_REQUIRED:") for event in final.events)
    assert any(event.startswith("APPROVED:") for event in final.events)
    assert executed == [
        "v105-final-goal-skill-001-research",
        "v105-final-goal-skill-002-coding",
        "v105-final-goal-skill-003-computer",
    ]

    rendered_final = render_progress(report)
    assert "100%" in rendered_final
    assert "RESULT    = GOAL_COMPLETE" in rendered_final
