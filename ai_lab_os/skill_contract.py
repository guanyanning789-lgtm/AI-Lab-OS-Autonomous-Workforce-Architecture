from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_lab_os.models import AgentKind


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
class SkillContract:
    skill_id: str
    name: str
    description: str
    inputs: tuple[SkillInputSpec, ...]
    required_agents: tuple[AgentKind, ...]
    permissions: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
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
            "metadata": dict(self.metadata),
        }
