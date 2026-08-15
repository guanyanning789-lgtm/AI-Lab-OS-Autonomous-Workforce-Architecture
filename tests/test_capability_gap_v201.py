from ai_lab_os.capability_gap import CapabilityGapReason, CapabilityStatus, assess_capability
from ai_lab_os.models import AgentKind
from ai_lab_os.skill_contract import SkillContract, SkillInputSpec
from ai_lab_os.skill_registry import SkillRegistry


def skill(skill_id: str, name: str, description: str, triggers: str) -> SkillContract:
    return SkillContract(
        skill_id=skill_id,
        name=name,
        description=description,
        inputs=(SkillInputSpec("goal", "natural-language goal"),),
        required_agents=(AgentKind.RESEARCH,),
        metadata={"triggers": triggers},
    )


def test_direct_capability_is_reported_without_gap() -> None:
    registry = SkillRegistry.from_skills((
        skill("disk-inspector", "Disk Inspector", "inspect disk storage and files", "disk,磁盘,磁碟"),
    ))
    result = assess_capability("检查我的磁盘空间", registry)
    assert result.status is CapabilityStatus.DIRECT
    assert result.can_execute_directly is True
    assert result.requires_capability_expansion is False
    assert result.selected_skill_id == "disk-inspector"
    assert result.gap_reason is None


def test_unknown_goal_becomes_structured_capability_gap() -> None:
    registry = SkillRegistry.from_skills((
        skill("disk-inspector", "Disk Inspector", "inspect disk storage and files", "disk,磁盘"),
    ))
    result = assess_capability("帮我设计一个从未注册过的雅思自适应课程系统", registry)
    assert result.status is CapabilityStatus.GAP
    assert result.requires_capability_expansion is True
    assert result.selected_skill_id is None
    assert result.gap_reason is CapabilityGapReason.NO_MATCH
    assert result.available_skill_ids == ("disk-inspector",)


def test_empty_registry_is_a_gap_not_a_crash() -> None:
    result = assess_capability("完成一个新任务", SkillRegistry())
    assert result.status is CapabilityStatus.GAP
    assert result.gap_reason is CapabilityGapReason.NO_MATCH
    assert result.available_skill_ids == ()


def test_ambiguous_match_is_reported_as_gap() -> None:
    registry = SkillRegistry.from_skills((
        skill("alpha", "Alpha", "shared capability", "shared"),
        skill("beta", "Beta", "shared capability", "shared"),
    ))
    result = assess_capability("shared", registry)
    assert result.status is CapabilityStatus.GAP
    assert result.gap_reason is CapabilityGapReason.AMBIGUOUS
    assert "ambiguous skill request" in (result.detail or "")


def test_whitespace_request_is_rejected() -> None:
    try:
        assess_capability("   ", SkillRegistry())
    except ValueError as exc:
        assert str(exc) == "capability request cannot be empty"
    else:
        raise AssertionError("expected ValueError")
