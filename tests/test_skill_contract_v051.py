from __future__ import annotations

import pytest

from ai_lab_os.models import AgentKind
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec


def _skill() -> SkillContract:
    return SkillContract(
        skill_id="research-and-verify",
        name="Research and Verify",
        description="Research a topic and verify the result on the computer.",
        inputs=(
            SkillInputSpec("topic", "Topic to research."),
            SkillInputSpec("max_sources", "Maximum source count.", required=False, default="5"),
        ),
        required_agents=(AgentKind.RESEARCH, AgentKind.COMPUTER),
        permissions=("web.search", "computer.mock"),
        success_criteria=("Research evidence is returned.", "Computer verification completes."),
    )


def test_skill_contract_binds_required_and_default_inputs() -> None:
    skill = _skill()
    assert skill.bind_inputs({"topic": "pytest"}) == {"topic": "pytest", "max_sources": "5"}


def test_skill_contract_rejects_missing_required_input() -> None:
    with pytest.raises(ValueError, match="missing required skill input: topic"):
        _skill().bind_inputs({})


def test_skill_contract_rejects_unknown_input() -> None:
    with pytest.raises(ValueError, match="unknown skill inputs: surprise"):
        _skill().bind_inputs({"topic": "pytest", "surprise": "x"})


def test_skill_contract_rejects_duplicate_agents() -> None:
    with pytest.raises(ValueError, match="required_agents cannot contain duplicates"):
        SkillContract(
            skill_id="bad",
            name="Bad",
            description="Bad skill.",
            inputs=(),
            required_agents=(AgentKind.CODING, AgentKind.CODING),
        )


def test_skill_contract_serializes_as_stable_manifest() -> None:
    manifest = _skill().to_dict()
    assert manifest["skill_id"] == "research-and-verify"
    assert manifest["version"] == "0.5.1"
    assert manifest["required_agents"] == ["research", "computer"]
    assert manifest["permissions"] == ["web.search", "computer.mock"]
    assert manifest["inputs"][1]["default"] == "5"
