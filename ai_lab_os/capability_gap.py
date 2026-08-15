from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_lab_os.skill_registry import SkillRegistry
from ai_lab_os.skill_selector import SkillSelection, select_skill


class CapabilityStatus(str, Enum):
    DIRECT = "direct"
    GAP = "gap"


class CapabilityGapReason(str, Enum):
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CapabilityAssessment:
    request: str
    status: CapabilityStatus
    selected_skill_id: str | None
    score: int | None
    matched_terms: tuple[str, ...]
    gap_reason: CapabilityGapReason | None
    detail: str | None
    available_skill_ids: tuple[str, ...]

    @property
    def can_execute_directly(self) -> bool:
        return self.status is CapabilityStatus.DIRECT

    @property
    def requires_capability_expansion(self) -> bool:
        return self.status is CapabilityStatus.GAP


def assess_capability(
    request: str,
    registry: SkillRegistry,
    *,
    min_score: int = 2,
) -> CapabilityAssessment:
    clean = request.strip()
    if not clean:
        raise ValueError("capability request cannot be empty")

    available = tuple(skill.skill_id for skill in registry.list())
    try:
        selection: SkillSelection = select_skill(clean, registry, min_score=min_score)
    except LookupError as exc:
        detail = str(exc)
        reason = (
            CapabilityGapReason.AMBIGUOUS
            if detail.startswith("ambiguous skill request:")
            else CapabilityGapReason.NO_MATCH
        )
        return CapabilityAssessment(
            request=clean,
            status=CapabilityStatus.GAP,
            selected_skill_id=None,
            score=None,
            matched_terms=(),
            gap_reason=reason,
            detail=detail,
            available_skill_ids=available,
        )

    return CapabilityAssessment(
        request=clean,
        status=CapabilityStatus.DIRECT,
        selected_skill_id=selection.skill.skill_id,
        score=selection.score,
        matched_terms=selection.matched_terms,
        gap_reason=None,
        detail=None,
        available_skill_ids=available,
    )
