from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityDecision:
    allowed: bool
    requires_approval: bool
    reason: str


@dataclass(frozen=True)
class ReliabilityPolicy:
    max_retries: int = 2
    require_approval_for_external_side_effects: bool = True

    def evaluate(
        self,
        *,
        risk: str,
        has_external_side_effects: bool,
        approved: bool,
    ) -> ReliabilityDecision:
        normalized_risk = risk.strip().lower()
        if normalized_risk not in {"low", "medium", "high"}:
            raise ValueError("risk must be low, medium, or high")

        requires_approval = (
            normalized_risk == "high"
            or (
                has_external_side_effects
                and self.require_approval_for_external_side_effects
            )
        )

        if requires_approval and not approved:
            return ReliabilityDecision(
                allowed=False,
                requires_approval=True,
                reason="human approval required",
            )

        return ReliabilityDecision(
            allowed=True,
            requires_approval=requires_approval,
            reason="allowed by reliability policy",
        )

    def can_retry(self, retries_used: int) -> bool:
        if retries_used < 0:
            raise ValueError("retries_used cannot be negative")
        return retries_used < self.max_retries
