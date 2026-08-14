from __future__ import annotations

from dataclasses import replace

from ai_lab_os.agent_router import AgentRouter
from ai_lab_os.goal_contract import GoalContract
from ai_lab_os.models import AgentKind
from ai_lab_os.supervisor_loop import (
    SupervisorPolicy,
    TaskExecutionResult,
    TaskExecutionStatus,
    run_supervisor_loop,
)
from ai_lab_os.task_planner import TaskPlanContract, plan_goal


def test_real_multistep_goal_routes_agents_recovers_and_reaches_goal_complete() -> None:
    goal = GoalContract(
        goal_id="goal-v036-e2e",
        natural_language_goal="Add a health endpoint and verify the complete change safely",
        success_criteria=(
            "The health endpoint reports healthy status",
            "Verification succeeds after implementation",
        ),
        constraints=("Use the smallest safe change",),
    )

    base_plan = plan_goal(goal)
    analyze, implement, verify = base_plan.tasks
    plan = TaskPlanContract(
        goal_id=base_plan.goal_id,
        planner_version=base_plan.planner_version,
        tasks=(
            replace(analyze, agent=AgentKind.RESEARCH),
            replace(implement, agent=AgentKind.CODING),
            replace(verify, agent=AgentKind.COMPUTER),
        ),
    )

    calls: list[str] = []
    coding_attempts = 0

    def research_executor(task):
        calls.append(f"research:{task.task_id}")
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS,
            message="Repository context and implementation path identified.",
        )

    def coding_executor(task):
        nonlocal coding_attempts
        coding_attempts += 1
        calls.append(f"coding:{task.task_id}:attempt={coding_attempts}")
        if coding_attempts == 1:
            return TaskExecutionResult(
                status=TaskExecutionStatus.FAILED,
                message="Transient implementation failure for recovery test.",
            )
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS,
            message="Implementation completed on retry.",
        )

    def computer_executor(task):
        calls.append(f"computer:{task.task_id}")
        return TaskExecutionResult(
            status=TaskExecutionStatus.SUCCESS,
            message="Verification evidence confirms all success criteria.",
        )

    router = AgentRouter.with_core_agents(
        coding=coding_executor,
        research=research_executor,
        computer=computer_executor,
    )

    result = run_supervisor_loop(
        plan,
        router.execute,
        policy=SupervisorPolicy(max_attempts_per_task=2, max_cycles=10),
    )

    assert result.status == "complete"
    assert result.completed_tasks == tuple(task.task_id for task in plan.tasks)
    assert result.failed_task_id is None
    assert result.events[-1] == "GOAL_COMPLETE"
    assert f"RETRY:{implement.task_id}" in result.events
    assert coding_attempts == 2
    assert calls == [
        f"research:{analyze.task_id}",
        f"coding:{implement.task_id}:attempt=1",
        f"coding:{implement.task_id}:attempt=2",
        f"computer:{verify.task_id}",
    ]
