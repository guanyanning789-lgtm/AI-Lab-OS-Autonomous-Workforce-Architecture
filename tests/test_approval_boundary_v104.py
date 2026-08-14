from __future__ import annotations

from ai_lab_os.approval_boundary import ApprovalAwareExecutor, ApprovalService
from ai_lab_os.models import AgentKind
from ai_lab_os.persistent_goal_store import JsonGoalStore
from ai_lab_os.product_runtime import ProductRuntime
from ai_lab_os.recovery_policy import RecoveryAction, decide_recovery
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec, SkillStepSpec
from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.supervisor_loop import TaskExecutionResult, TaskExecutionStatus
from ai_lab_os.task_planner import PlannedTaskKind
from ai_lab_os.unified_goal_service import GoalSubmissionRequest


def _registry() -> SkillRegistry:
    skill = SkillContract(
        skill_id="computer-action",
        name="Computer Action",
        description="Perform a real computer action.",
        inputs=(SkillInputSpec("topic", "Action request."),),
        required_agents=(AgentKind.COMPUTER,),
        metadata={"triggers": "电脑,電腦,computer,click"},
        steps=(SkillStepSpec(
            "computer",
            PlannedTaskKind.VERIFY,
            AgentKind.COMPUTER,
            "Perform {topic}.",
            metadata_templates={"action": "click"},
        ),),
    )
    return SkillRegistry.from_skills((skill,))


def test_real_computer_action_waits_for_explicit_approval_then_resumes(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    approvals = ApprovalService(store)
    calls: list[str] = []

    def inner(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "real action completed")

    gated = ApprovalAwareExecutor(inner, approvals, real_computer_actions_enabled=True)
    runtime = ProductRuntime(
        _registry(),
        gated,
        store,
        approval_service=approvals,
    )

    submitted = runtime.submit(GoalSubmissionRequest(goal="电脑 click test", goal_id="approval-goal"))
    waiting = runtime.get_goal("approval-goal")
    assert submitted.status == "approval_required"
    assert waiting.status == "approval_required"
    assert waiting.tasks[0].status == "awaiting_approval"
    assert calls == []
    assert decide_recovery(store.load("approval-goal")).action is RecoveryAction.NONE

    idle_tick = runtime.tick()
    assert idle_tick.recovery.actionable_goals == 0
    assert calls == []

    runtime.approve("approval-goal", waiting.resume_cursor or "")
    approved = runtime.get_goal("approval-goal")
    assert approved.status == "in_progress"
    assert approved.tasks[0].status == "ready"

    recovery_tick = runtime.tick()
    final = runtime.get_goal("approval-goal")
    assert recovery_tick.recovery.actionable_goals == 1
    assert final.status == "complete"
    assert final.progress_percent == 100
    assert final.resume_cursor is None
    assert len(calls) == 1
    assert "GOAL_COMPLETE" in final.events


def test_reject_keeps_sensitive_action_unexecuted(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    approvals = ApprovalService(store)
    calls: list[str] = []

    def inner(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "done")

    runtime = ProductRuntime(
        _registry(),
        ApprovalAwareExecutor(inner, approvals, real_computer_actions_enabled=True),
        store,
        approval_service=approvals,
    )
    runtime.submit(GoalSubmissionRequest(goal="电脑 click test", goal_id="rejected-goal"))
    waiting = runtime.get_goal("rejected-goal")
    runtime.reject_approval("rejected-goal", waiting.resume_cursor or "")

    assert runtime.get_goal("rejected-goal").status == "paused"
    assert runtime.tick().recovery.actionable_goals == 0
    assert calls == []


def test_dry_run_or_non_real_mode_does_not_require_approval(tmp_path) -> None:
    store = JsonGoalStore(tmp_path / "goals.json")
    approvals = ApprovalService(store)
    calls: list[str] = []

    def inner(task):
        calls.append(task.task_id)
        return TaskExecutionResult(TaskExecutionStatus.SUCCESS, "dry-run verified")

    runtime = ProductRuntime(
        _registry(),
        ApprovalAwareExecutor(inner, approvals, real_computer_actions_enabled=False),
        store,
        approval_service=approvals,
    )
    result = runtime.submit(GoalSubmissionRequest(goal="电脑 click test", goal_id="dry-goal"))
    assert result.status == "complete"
    assert len(calls) == 1
