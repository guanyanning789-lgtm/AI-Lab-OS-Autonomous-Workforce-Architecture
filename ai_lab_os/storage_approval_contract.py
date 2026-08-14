from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ai_lab_os.storage_migration_blueprint import MigrationBlueprintItem


@dataclass(frozen=True)
class ApprovalContractItem:
    source: str
    destination: str
    sha256: str
    action: str
    risk: str


@dataclass(frozen=True)
class ApprovalContract:
    items: tuple[ApprovalContractItem, ...]
    approved: bool
    executable: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_approval_contract(
    blueprint: tuple[MigrationBlueprintItem, ...],
    *,
    limit: int = 3,
) -> ApprovalContract:
    selected: list[ApprovalContractItem] = []
    for item in blueprint:
        source = Path(item.source)
        destination = Path(item.destination)
        if item.risk != "LOW" or not item.rollback_ready:
            continue
        if source.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        if not source.exists() or not source.is_file() or destination.exists():
            continue
        selected.append(
            ApprovalContractItem(
                source=str(source),
                destination=str(destination),
                sha256=_sha256(source),
                action=item.action.value,
                risk=item.risk,
            )
        )
        if len(selected) >= max(1, limit):
            break
    return ApprovalContract(tuple(selected), approved=False, executable=False)


def render_approval_contract(contract: ApprovalContract) -> str:
    lines = ["EXACT APPROVAL CONTRACT (PREVIEW ONLY)"]
    for index, item in enumerate(contract.items, 1):
        lines.extend([
            f"  {index}. source      = {item.source}",
            f"     destination = {item.destination}",
            f"     action      = {item.action}",
            f"     risk        = {item.risk}",
            f"     sha256      = {item.sha256}",
        ])
    lines.append(f"CONTRACT_ITEMS = {len(contract.items)}")
    lines.append("APPROVED       = False")
    lines.append("EXECUTABLE     = False")
    lines.append("NOTE           = Any path/hash/action mismatch invalidates future approval.")
    return "\n".join(lines)
