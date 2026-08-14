from __future__ import annotations

from dataclasses import dataclass

from ai_lab_os.skill_contract import SkillContract, SkillStepSpec
from ai_lab_os.task_planner import PlannedTask, TaskPlanContract


@dataclass(frozen=True)
class CompiledSkillPlan:
    skill_id: str
    bound_inputs: dict[str, str]
    plan: TaskPlanContract


class _StrictTemplateValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        raise ValueError(f"unknown skill template variable: {key}")


def _render(template: str, values: dict[str, str]) -> str:
    try:
        rendered = template.format_map(_StrictTemplateValues(values)).strip()
    except (ValueError, KeyError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("unknown skill template variable"):
            raise
        raise ValueError(f"invalid skill template: {template}") from exc
    if not rendered:
        raise ValueError("skill template rendered to empty text")
    return rendered


def _task_id(goal_id: str, step: SkillStepSpec, sequence: int) -> str:
    return f"{goal_id}-skill-{sequence:03d}-{step.step_id}"


def compile_skill_plan(
    skill: SkillContract,
    supplied_inputs: dict[str, str],
    *,
    goal_id: str,
) -> CompiledSkillPlan:
    clean_goal_id = goal_id.strip()
    if not clean_goal_id:
        raise ValueError("goal_id cannot be empty")
    if not skill.steps:
        raise ValueError(f"skill has no executable steps: {skill.skill_id}")

    bound = skill.bind_inputs(supplied_inputs)
    values = {
        **bound,
        "skill_id": skill.skill_id,
        "skill_name": skill.name,
        "goal_id": clean_goal_id,
    }

    id_by_step = {
        step.step_id: _task_id(clean_goal_id, step, sequence)
        for sequence, step in enumerate(skill.steps, start=1)
    }
    tasks: list[PlannedTask] = []
    permission_text = ",".join(skill.permissions)

    for sequence, step in enumerate(skill.steps, start=1):
        metadata = {
            key: _render(template, values)
            for key, template in step.metadata_templates.items()
        }
        metadata.update(
            {
                "skill_id": skill.skill_id,
                "skill_version": skill.version,
                "skill_permissions": permission_text,
            }
        )
        step_criteria = step.success_criteria or skill.success_criteria
        tasks.append(
            PlannedTask(
                task_id=id_by_step[step.step_id],
                goal_id=clean_goal_id,
                sequence=sequence,
                kind=step.kind,
                description=_render(step.description_template, values),
                agent=step.agent,
                success_criteria=tuple(_render(item, values) for item in step_criteria),
                depends_on=tuple(id_by_step[item] for item in step.depends_on),
                metadata=metadata,
            )
        )

    return CompiledSkillPlan(
        skill_id=skill.skill_id,
        bound_inputs=dict(bound),
        plan=TaskPlanContract(
            goal_id=clean_goal_id,
            tasks=tuple(tasks),
            planner_version="v0.5.3-skill-compiler",
        ),
    )
