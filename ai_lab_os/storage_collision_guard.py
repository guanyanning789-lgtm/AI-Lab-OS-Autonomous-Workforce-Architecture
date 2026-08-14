from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ai_lab_os.storage_path_planner import MigrationProposal, MigrationRisk


class GuardDecision(str, Enum):
    SAFE_TO_PLAN = "safe_to_plan"
    SAME_CONTENT = "same_content"
    COLLISION = "collision"
    REFERENCE_RISK = "reference_risk"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GuardResult:
    proposal: MigrationProposal
    decision: GuardDecision
    executable: bool
    reason: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def guard_migration(proposal: MigrationProposal) -> GuardResult:
    if proposal.risk is MigrationRisk.BLOCKED or proposal.destination is None:
        return GuardResult(proposal, GuardDecision.BLOCKED, False, "proposal has no permitted destination")

    source = Path(proposal.source)
    destination = Path(proposal.destination)
    source_parts = {part.lower() for part in source.parts}

    if ".git" in source_parts or source.suffix.lower() in {".py", ".ps1", ".bat", ".cmd", ".exe", ".dll"}:
        return GuardResult(proposal, GuardDecision.REFERENCE_RISK, False, "code/executable path may be referenced; dependency analysis required")

    if destination.exists():
        try:
            if source.is_file() and destination.is_file() and source.stat().st_size == destination.stat().st_size:
                if _sha256(source) == _sha256(destination):
                    return GuardResult(proposal, GuardDecision.SAME_CONTENT, False, "destination already contains identical bytes; treat as duplicate, never overwrite")
        except OSError:
            pass
        return GuardResult(proposal, GuardDecision.COLLISION, False, "destination already exists with different or unverifiable content; never overwrite")

    return GuardResult(proposal, GuardDecision.SAFE_TO_PLAN, False, "no collision detected; still requires explicit approval before any move")


def guard_plan(proposals: tuple[MigrationProposal, ...]) -> tuple[GuardResult, ...]:
    return tuple(guard_migration(item) for item in proposals)
