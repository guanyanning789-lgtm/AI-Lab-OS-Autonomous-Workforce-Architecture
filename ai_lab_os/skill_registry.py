from __future__ import annotations

from dataclasses import dataclass, field

from ai_lab_os.skill_contract import SkillContract


@dataclass
class SkillRegistry:
    _skills: dict[str, SkillContract] = field(default_factory=dict)

    def register(self, skill: SkillContract) -> None:
        if skill.skill_id in self._skills:
            raise ValueError(f"skill already registered: {skill.skill_id}")
        self._skills[skill.skill_id] = skill

    def replace(self, skill: SkillContract) -> None:
        self._skills[skill.skill_id] = skill

    def unregister(self, skill_id: str) -> SkillContract:
        key = skill_id.strip()
        if not key:
            raise ValueError("skill_id cannot be empty")
        try:
            return self._skills.pop(key)
        except KeyError as exc:
            raise LookupError(f"skill not registered: {key}") from exc

    def get(self, skill_id: str) -> SkillContract:
        key = skill_id.strip()
        if not key:
            raise ValueError("skill_id cannot be empty")
        try:
            return self._skills[key]
        except KeyError as exc:
            raise LookupError(f"skill not registered: {key}") from exc

    def contains(self, skill_id: str) -> bool:
        key = skill_id.strip()
        return bool(key) and key in self._skills

    def list(self) -> tuple[SkillContract, ...]:
        return tuple(self._skills[key] for key in sorted(self._skills))

    def manifests(self) -> tuple[dict[str, object], ...]:
        return tuple(skill.to_dict() for skill in self.list())

    @classmethod
    def from_skills(cls, skills: tuple[SkillContract, ...]) -> "SkillRegistry":
        registry = cls()
        for skill in skills:
            registry.register(skill)
        return registry
