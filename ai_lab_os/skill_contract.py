from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_lab_os.models import AgentKind
from ai_lab_os.task_planner import PlannedTaskKind


@dataclass(frozen=True)
class SkillInputSpec:
    name: str
    description: str
    required: bool = True
    default: str | None = None

    def __post_init__(self) -> None:
        name = self.name.strip()
        description = self.description.strip()
        if not name:
            raise ValueError("skill input name cannot be empty")
        if not description:
            raise ValueError("skill input description cannot be empty")
        if self.required and self.default is not None:
            raise ValueError("required skill input cannot define a default")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class SkillStepSpec:
    step_id: str
    kind: PlannedTaskKind
    agent: AgentKind
    description_template: str
    depends_on: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    metadata_templates: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        step_id = self.step_id.strip()
        description_template = self.description_template.strip()
        if not step_id:
            raise ValueError("skill step_id cannot be empty")
        if not description_template:
            raise ValueError("skill description_template cannot be empty")
        dependencies = tuple(item.strip() for item in self.depends_on if item.strip())
        criteria = tuple(item.strip() for item in self.success_criteria if item.strip())
        if step_id in dependencies:
            raise ValueError("skill step cannot depend on itself")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("skill step dependencies cannot contain duplicates")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata_templates.items()):
            raise ValueError("skill step metadata templates must be strings")
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "description_template", description_template)
        object.__setattr__(self, "depends_on", dependencies)
        object.__setattr__(self, "success_criteria", criteria)


@dataclass(frozen=True)
class SkillContract:
    skill_id: str
    name: str
    description: str
    inputs: tuple[SkillInputSpec, ...]
    required_agents: tuple[AgentKind, ...]
    permissions: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    steps: tuple[SkillStepSpec, ...] = ()
    version: str = "0.5.1"
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        skill_id = self.skill_id.strip()
        name = self.name.strip()
        description = self.description.strip()
        version = self.version.strip()
        if not skill_id:
            raise ValueError("skill_id cannot be empty")
        if not name:
            raise ValueError("skill name cannot be empty")
        if not description:
            raise ValueError("skill description cannot be empty")
        if not version:
            raise ValueError("skill version cannot be empty")
        input_names = [item.name for item in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError("skill input names must be unique")
        if not self.required_agents:
            raise ValueError("skill must require at least one agent")
        if len(self.required_agents) != len(set(self.required_agents)):
            raise ValueError("required_agents cannot contain duplicates")
        permissions = tuple(item.strip() for item in self.permissions if item.strip())
        criteria = tuple(item.strip() for item in self.success_criteria if item.strip())
        if len(permissions) != len(set(permissions)):
            raise ValueError("permissions cannot contain duplicates")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.metadata.items()):
            raise ValueError("skill metadata keys and values must be strings")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("skill step ids must be unique")
        known_steps: set[str] = set()
        for step in self.steps:
            unknown = sorted(set(step.depends_on) - known_steps)
            if unknown:
                raise ValueError(
                    f"skill step {step.step_id} depends on unknown or later steps: {', '.join(unknown)}"
                )
            if step.agent not in self.required_agents:
                raise ValueError(
                    f"skill step {step.step_id} uses undeclared agent: {step.agent.value}"
                )
            known_steps.add(step.step_id)

        object.__setattr__(self, "skill_id", skill_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "permissions", permissions)
        object.__setattr__(self, "success_criteria", criteria)

    def bind_inputs(self, supplied: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(supplied) - {item.name for item in self.inputs})
        if unknown:
            raise ValueError(f"unknown skill inputs: {', '.join(unknown)}")
        bound: dict[str, str] = {}
        for spec in self.inputs:
            value = supplied.get(spec.name)
            if value is not None:
                value = value.strip()
            if value:
                bound[spec.name] = value
                continue
            if spec.default is not None:
                bound[spec.name] = spec.default
                continue
            if spec.required:
                raise ValueError(f"missing required skill input: {spec.name}")
        return bound

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "inputs": [
                {
                    "name": item.name,
                    "description": item.description,
                    "required": item.required,
                    "default": item.default,
                }
                for item in self.inputs
            ],
            "required_agents": [agent.value for agent in self.required_agents],
            "permissions": list(self.permissions),
            "success_criteria": list(self.success_criteria),
            "steps": [
                {
                    "step_id": step.step_id,
                    "kind": step.kind.value,
                    "agent": step.agent.value,
                    "description_template": step.description_template,
                    "depends_on": list(step.depends_on),
                    "success_criteria": list(step.success_criteria),
                    "metadata_templates": dict(step.metadata_templates),
                }
                for step in self.steps
            ],
            "metadata": dict(self.metadata),
        }
