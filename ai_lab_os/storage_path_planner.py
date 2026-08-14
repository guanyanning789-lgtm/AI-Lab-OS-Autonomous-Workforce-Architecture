from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition


class MigrationRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PathRule:
    category: str
    destination_root: str
    suffixes: tuple[str, ...]


@dataclass(frozen=True)
class MigrationProposal:
    source: str
    destination: str | None
    category: str
    risk: MigrationRisk
    approval_required: bool
    reason: str


DEFAULT_RULES = (
    PathRule("AI Models", r"D:\AI-Lab\Models", (".safetensors", ".gguf", ".ckpt", ".pt", ".pth")),
    PathRule("Archives", r"D:\Archive", (".zip", ".7z", ".rar", ".tar", ".gz")),
    PathRule("Video", r"D:\AI-Lab\Media\Video", (".mp4", ".mov", ".mkv", ".webm")),
    PathRule("Images", r"D:\AI-Lab\Media\Images", (".png", ".jpg", ".jpeg", ".webp")),
    PathRule("Documents", r"D:\Knowledge\Documents", (".pdf", ".docx", ".txt", ".md")),
)


def _rule_for(path: Path, rules: tuple[PathRule, ...]) -> PathRule | None:
    suffix = path.suffix.lower()
    return next((rule for rule in rules if suffix in rule.suffixes), None)


def propose_path(candidate: FileCandidate, *, rules: tuple[PathRule, ...] = DEFAULT_RULES) -> MigrationProposal:
    source = Path(candidate.path)
    if candidate.disposition is StorageDisposition.PROTECTED:
        return MigrationProposal(candidate.path, None, "Protected", MigrationRisk.BLOCKED, False, "protected paths are never migrated")

    rule = _rule_for(source, rules)
    if rule is None:
        return MigrationProposal(candidate.path, None, "Unclassified", MigrationRisk.MEDIUM, True, "no canonical destination rule; manual review required")

    destination = str(Path(rule.destination_root) / source.name)
    if Path(destination) == source:
        return MigrationProposal(candidate.path, destination, rule.category, MigrationRisk.LOW, False, "already in canonical location")

    risk = MigrationRisk.HIGH if candidate.disposition is StorageDisposition.REVIEW else MigrationRisk.MEDIUM
    return MigrationProposal(
        candidate.path,
        destination,
        rule.category,
        risk,
        True,
        "canonical path suggestion only; references and collisions must be verified before move",
    )


def build_migration_plan(candidates: tuple[FileCandidate, ...], *, rules: tuple[PathRule, ...] = DEFAULT_RULES) -> tuple[MigrationProposal, ...]:
    return tuple(propose_path(candidate, rules=rules) for candidate in candidates)
