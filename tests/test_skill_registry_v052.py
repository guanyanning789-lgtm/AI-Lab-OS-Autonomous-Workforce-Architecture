from __future__ import annotations

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.skill_contract import SkillContract
from ai_lab_os.skill_registry import SkillRegistry


def _skill(skill_id: str, name: str) -> SkillContract:
    return SkillContract(
        skill_id=skill_id,
        name=name,
        description=f"{name} description",
        inputs=(),
        required_agents=(AgentKind.CODING,),
    )


def test_registry_registers_and_gets_skill() -> None:
    registry = SkillRegistry()
    skill = _skill("alpha", "Alpha")
    registry.register(skill)
    assert registry.contains("alpha") is True
    assert registry.get("alpha") is skill


def test_registry_rejects_duplicate_registration() -> None:
    registry = SkillRegistry()
    registry.register(_skill("alpha", "Alpha"))
    with pytest.raises(ValueError, match="skill already registered: alpha"):
        registry.register(_skill("alpha", "Other"))


def test_registry_replace_updates_existing_skill() -> None:
    registry = SkillRegistry.from_skills((_skill("alpha", "Alpha"),))
    replacement = _skill("alpha", "Alpha v2")
    registry.replace(replacement)
    assert registry.get("alpha") is replacement


def test_registry_lists_skills_in_stable_id_order() -> None:
    registry = SkillRegistry.from_skills((
        _skill("zeta", "Zeta"),
        _skill("alpha", "Alpha"),
    ))
    assert [skill.skill_id for skill in registry.list()] == ["alpha", "zeta"]
    assert [item["skill_id"] for item in registry.manifests()] == ["alpha", "zeta"]


def test_registry_unregisters_and_fails_closed_for_missing_skill() -> None:
    registry = SkillRegistry.from_skills((_skill("alpha", "Alpha"),))
    removed = registry.unregister("alpha")
    assert removed.skill_id == "alpha"
    assert registry.contains("alpha") is False
    with pytest.raises(LookupError, match="skill not registered: alpha"):
        registry.get("alpha")
