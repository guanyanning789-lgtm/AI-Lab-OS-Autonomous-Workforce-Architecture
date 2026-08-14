from __future__ import annotations

from dataclasses import dataclass, replace

from ai_lab_os.persistent_goal_store import PersistentGoalState
from ai_lab_os.task_planner import PlannedTask, TaskPlanContract


@dataclass(frozen=True)
class ReplanCandidate:
    original_plan: TaskPlanContract
    candidate_plan: TaskPlanContract
    failed_task_id: str
    reason: str
    changed_task_ids: tuple[str, ...]


def _failed_task_id(state: PersistentGoalState) -> str:
    if state.resume_cursor:
        return state.resume_cursor
    for task in state.tasks:
        if task.status in {"failed", "replan"}:
            return task.task_id
    raise ValueError("replan state has no failed/resume task")


def build_bounded_replan(state: PersistentGoalState) -> ReplanCandidate:
    """Build a deterministic fail-closed replan candidate.

    V0.7.3 intentionally does not invent new agents, permissions, dependencies,
    task ids, or task ordering. It only annotates the failed task so the existing
    executor receives explicit recovery context while the original contract
    topology remains unchanged.
    """

    original = TaskPlanContract.from_dict(state.plan)
    failed_id = _failed_task_id(state)
    known_ids = {task.task_id for task in original.tasks}
    if failed_id not in known_ids:
        raise ValueError("replan target is not present in the persisted plan")

    persistent_task = next((task for task in state.tasks if task.task_id == failed_id), None)
    failure_message = "" if persistent_task is None else persistent_task.message.strip()
    reason = failure_message or "previous execution requested replan"

    tasks: list[PlannedTask] = []
    for task in original.tasks:
        if task.task_id != failed_id:
            tasks.append(task)
            continue
        metadata = dict(task.metadata)
        metadata.update({
            "recovery_mode": "replan",
            "replan_reason": reason,
            "previous_attempts": str(0 if persistent_task is None else persistent_task.attempts),
        })
        tasks.append(
            replace(
                task,
                description=(
                    f"{task.description} Recovery context: previous execution failed; "
                    f"re-evaluate the smallest safe approach before executing. Reason: {reason}"
                ),
                metadata=metadata,
            )
        )

    candidate = TaskPlanContract(
        goal_id=original.goal_id,
        tasks=tuple(tasks),
        planner_version="v0.7.3-replan",
    )
    validate_replan_candidate(original, candidate, failed_task_id=failed_id)
    return ReplanCandidate(
        original_plan=original,
        candidate_plan=candidate,
        failed_task_id=failed_id,
        reason=reason,
        changed_task_ids=(failed_id,),
    )


def validate_replan_candidate(
    original: TaskPlanContract,
    candidate: TaskPlanContract,
    *,
    failed_task_id: str,
) -> None:
    """Reject replans that expand execution authority or rewrite topology."""

    if candidate.goal_id != original.goal_id:
        raise ValueError("replan cannot change goal_id")
    if len(candidate.tasks) != len(original.tasks):
        raise ValueError("replan cannot add or remove tasks")

    for before, after in zip(original.tasks, candidate.tasks):
        if before.task_id != after.task_id or before.sequence != after.sequence:
            raise ValueError("replan cannot change task identity or ordering")
        if before.kind != after.kind:
            raise ValueError("replan cannot change task kind")
        if before.agent != after.agent:
            raise ValueError("replan cannot change assigned agent")
        if before.depends_on != after.depends_on:
            raise ValueError("replan cannot change dependencies")
        if before.success_criteria != after.success_criteria:
            raise ValueError("replan cannot weaken or change success criteria")
        if before.task_id != failed_task_id and before != after:
            raise ValueError("replan may only modify the failed task")

    failed = next(task for task in candidate.tasks if task.task_id == failed_task_id)
    if failed.metadata.get("recovery_mode") != "replan":
        raise ValueError("replanned task must declare recovery_mode=replan")
